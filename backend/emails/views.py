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
        qs = EmailMessage.objects.filter(
            mailbox__user=request.user,
            processed=False
        )

        if mailbox_id is not None:
            qs = qs.filter(mailbox_id=mailbox_id)

        emails = qs.order_by('-received_at')[:50]
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

            return Response({"status": "sent", "to": data['to']})
        except Exception as e:
            return Response(
                {"error": f"SMTP error: {str(e)}"},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )