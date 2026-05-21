import imaplib
import email
from email import policy
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from email.parser import BytesParser

from django.utils import timezone

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as drf_status
from rest_framework.permissions import IsAuthenticated

from .models import Mailbox, EmailMessage
from .serializers import (
    EmailMessageSerializer,
    SendEmailSerializer,
    MailboxSerializer,
    CreateMailboxSerializer,
)
from django_q.tasks import async_task




def parse_email_message(raw_bytes):
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    subject = msg.get('Subject', '')
    sender = msg.get('From', '')
    body_text = ''
    body_html = ''

    body_part_text = msg.get_body(preferencelist=('plain',))
    if body_part_text:
        body_text = body_part_text.get_content()

    body_part_html = msg.get_body(preferencelist=('html',))
    if body_part_html:
        body_html = body_part_html.get_content()

    return subject, sender, body_text, body_html


class MailboxViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MailboxSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        return Mailbox.objects.filter(user=self.request.user).order_by('name')

    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateMailboxSerializer
        return MailboxSerializer


class FetchEmailsView(APIView):
    permission_classes = [IsAuthenticated]

    def _fetch_from_mailbox(self, mailbox):
        count = 0
        try:
            mail = imaplib.IMAP4_SSL(mailbox.imap_host, mailbox.imap_port)
            mail.login(mailbox.username, mailbox.password)
            mail.select('INBOX')

            status, messages = mail.search(None, 'ALL')
            if status != 'OK':
                return 0

            uids = messages[0].split()
            if not uids:
                mail.logout()
                return 0

            for uid in uids[-50:]:
                uid_str = uid.decode()

                # TYMCZASOWO ZAKOMENTOWANE NA POTRZEBY TESTÓW:
                # if EmailMessage.objects.filter(mailbox=mailbox, uid=uid_str).exists():
                #     continue

                status, msg_data = mail.fetch(uid, '(RFC822)')
                if status != 'OK' or not msg_data:
                    continue

                raw_email = msg_data[0][1]
                subject, sender, body_text, body_html = parse_email_message(raw_email)

                # Używamy update_or_create, aby zresetować stan e-maila przy każdym fetchu
                new_email, created = EmailMessage.objects.update_or_create(
                    mailbox=mailbox,
                    uid=uid_str,
                    defaults={
                        'subject': subject,
                        'sender': sender,
                        'body_text': body_text,
                        'body_html': body_html,
                        'processed': False,  # Resetujemy status przetwarzania
                        'category': '',  # Czyścimy starą kategorię
                        'ai_summary': '',  # Czyścimy stare streszczenie
                        'ai_draft_reply': '',  # Czyścimy stary draft
                        'priority_score': None,  # Resetujemy priorytet
                        'received_at': timezone.now()  # Aktualizujemy czas (opcjonalnie)
                    }
                )
                count += 1

                async_task('emails.tasks.agent_classify_email', new_email.id)

            mail.logout()
        except Exception as e:
            print(f"Error reading from {mailbox.username}: {e}")
            return 0

        return count

    def post(self, request):
        mailboxes = Mailbox.objects.filter(user=request.user)

        if not mailboxes.exists():
            return Response(
                {"message": "No mailboxes configured"},
                status=drf_status.HTTP_400_BAD_REQUEST
            )

        total_fetched = 0
        report = {}

        for mb in mailboxes:
            fetched_count = self._fetch_from_mailbox(mb)
            total_fetched += fetched_count
            report[mb.username] = fetched_count

        return Response({
            "status": "completed",
            "total_new_emails": total_fetched,
            "details": report
        })


class ClearEmailsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        deleted_count, _ = EmailMessage.objects.filter(mailbox__user=request.user).delete()

        return Response({
            "message": "Emails cleared successfully",
            "deleted_count": deleted_count
        })


class ListEmailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, mailbox_id=None):
        qs = EmailMessage.objects.filter(mailbox__user=request.user)

        if mailbox_id is not None:
            qs = qs.filter(mailbox_id=mailbox_id)

        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        processed = request.query_params.get('processed')
        if processed is not None:
            if processed.lower() in ('true', '1', 'yes'):
                qs = qs.filter(processed=True)
            elif processed.lower() in ('false', '0', 'no'):
                qs = qs.filter(processed=False)

        limit = min(int(request.query_params.get('limit', 100)), 500)
        emails = qs.order_by('-received_at')[:limit]
        serializer = EmailMessageSerializer(emails, many=True)
        return Response(serializer.data)


class TestListEmailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, mailbox_id=None):
        qs = EmailMessage.objects.filter(
            mailbox__user=request.user,
        )

        emails = qs.order_by('-received_at')[:1000]
        serializer = EmailMessageSerializer(emails, many=True)
        return Response(serializer.data)


class SendEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SendEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=drf_status.HTTP_400_BAD_REQUEST)

        mailbox = serializer.validated_data['mailbox']

        if mailbox.user != request.user:
            return Response(
                {"error": "Mailbox not found"},
                status=drf_status.HTTP_404_NOT_FOUND
            )

        data = serializer.validated_data

        msg = MIMEMultipart()
        msg['From'] = mailbox.username
        msg['To'] = data['to']
        msg['Subject'] = data['subject']
        msg.attach(MIMEText(data['body'], 'plain'))

        try:
            host = mailbox.smtp_host
            port = mailbox.smtp_port

            server = smtplib.SMTP_SSL(host, port)
            server.login(mailbox.username, mailbox.password)
            server.send_message(msg)
            server.quit()

            # >>> NOWE: zapisz wysłaną wiadomość jako EmailMessage <<<

            # Uwaga: jeśli chcesz, żeby wysłane maile też były
            # klasyfikowane/streszczane przez agentów, ustaw processed=False
            # i odpal async_task tak jak przy odbieranych wiadomościach.

            EmailMessage.objects.create(
                mailbox=mailbox,
                subject=data['subject'],
                sender=mailbox.username,
                body_text=data['body'],
                body_html='',
                uid=f"sent-{timezone.now().timestamp()}",
                processed=True,              # albo False, jeśli chcesz przepuszczać przez AI
                processed_at=timezone.now()  # opcjonalnie, skoro processed=True
            )

            return Response({"status": "sent", "to": data['to']})

        except Exception as e:
            return Response(
                {"error": f"SMTP error: {str(e)}"},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ThreadSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, email_id):
        try:
            email = EmailMessage.objects.get(
                id=email_id,
                mailbox__user=request.user
            )
        except EmailMessage.DoesNotExist:
            return Response(
                {"error": "Email not found"},
                status=drf_status.HTTP_404_NOT_FOUND
            )

        # Uproszczone „oczyszczenie” tematu z prefixów typu "Re: "
        base_subject = email.subject
        for prefix in ["Re: ", "RE: ", "Fw: ", "Fwd: ", "Odp: "]:
            if base_subject.startswith(prefix):
                base_subject = base_subject[len(prefix):].strip()

        # Bierzemy wszystkie maile z tego samego mailboxa i z podobnym tematem
        thread_emails = EmailMessage.objects.filter(
            mailbox=email.mailbox,
            subject__icontains=base_subject
        ).order_by('received_at')

        if not thread_emails.exists():
            return Response(
                {"error": "No emails found for this thread"},
                status=drf_status.HTTP_404_NOT_FOUND
            )

        # Sklejamy historię rozmowy
        conversation_text = ""
        for msg in thread_emails:
            conversation_text += (
                f"OD: {msg.sender}\n"
                f"TEMAT: {msg.subject}\n"
                f"TREŚĆ:\n{(msg.body_text or msg.body_html)[:1000]}\n\n"
                "----------\n\n"
            )

        from .tasks import query_ollama  # import lokalny, żeby uniknąć cykli

        prompt = f"""
            Streszcz historię mailową poniżej.
            
            Cel:
            - Wyjaśnij po polsku, o czym była rozmowa między klientem a firmą.
            - Zrób podsumowanie w 3-6 zdaniach.
            - Uwzględnij:
              - o co chodziło (jaki problem / temat),
              - jakie były główne ustalenia,
              - czy coś zostało jeszcze do zrobienia.
            
            Historia maili (od najstarszego do najnowszego):
            
            {conversation_text[:6000]}
            """

        summary = query_ollama(prompt).strip()

        # Zapisujemy podsumowanie do głównego maila wątku (tego, o który pytaliśmy)
        email.thread_summary = summary
        email.save(update_fields=['thread_summary'])

        return Response({
            "email_id": email.id,
            "subject": email.subject,
            "thread_summary": summary,
        })