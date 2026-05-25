import imaplib
import uuid
from email import policy
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from email.parser import BytesParser

from django.db.models import Count
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
from .threading import (
    collapse_to_latest_per_thread,
    extract_message_id,
    get_thread_messages,
    parse_email_date,
    parse_references,
    resolve_thread_id,
)
from django_q.tasks import async_task


def parse_email_message(raw_bytes):
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    subject = msg.get('Subject', '') or ''
    sender = msg.get('From', '') or ''
    body_text = ''
    body_html = ''

    body_part_text = msg.get_body(preferencelist=('plain',))
    if body_part_text:
        body_text = body_part_text.get_content()

    body_part_html = msg.get_body(preferencelist=('html',))
    if body_part_html:
        body_html = body_part_html.get_content()

    message_id = extract_message_id(msg.get('Message-ID', ''))
    in_reply_to = extract_message_id(msg.get('In-Reply-To', ''))
    references = msg.get('References', '') or ''
    received_at = parse_email_date(msg)

    return {
        'subject': subject,
        'sender': sender,
        'body_text': body_text,
        'body_html': body_html,
        'message_id': message_id,
        'in_reply_to': in_reply_to,
        'references': references,
        'received_at': received_at,
    }


def _thread_counts_for_emails(emails, include_hidden: bool = False):
    thread_ids = {e.thread_id for e in emails if e.thread_id}
    if not thread_ids:
        return {}
    qs = EmailMessage.objects.filter(thread_id__in=thread_ids)
    if not include_hidden:
        qs = qs.filter(is_hidden=False)
    rows = qs.values('thread_id').annotate(count=Count('id'))
    return {row['thread_id']: row['count'] for row in rows}


def _get_user_email(request, email_id):
    try:
        return EmailMessage.objects.get(
            id=email_id,
            mailbox__user=request.user,
        )
    except EmailMessage.DoesNotExist:
        return None


def _queryset_for_user(request, mailbox_id=None, include_hidden=False):
    qs = EmailMessage.objects.filter(mailbox__user=request.user)
    if mailbox_id is not None:
        qs = qs.filter(mailbox_id=mailbox_id)
    if not include_hidden:
        qs = qs.filter(is_hidden=False)
    return qs


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

            status, folders = mail.list()
            if status != 'OK':
                return 0

            for folder_data in folders:
                folder_str = folder_data.decode()
                folder_name = folder_str.split(' "/" ')[-1]

                if '"' in folder_name:
                    folder_name = folder_name.strip('"')

                if any(skip in folder_name.lower() for skip in ['trash', 'kosz', 'spam']):
                    continue

                status, _ = mail.select(f'"{folder_name}"', readonly=True)
                if status != 'OK':
                    continue

                status, messages = mail.search(None, 'ALL')
                if status != 'OK':
                    continue

                uids = messages[0].split()
                if not uids:
                    continue

                for uid in uids[-100:]:
                    uid_str = f"{folder_name}-{uid.decode()}"

                    status, msg_data = mail.fetch(uid, '(RFC822)')
                    if status != 'OK' or not msg_data:
                        continue

                    raw_email = msg_data[0][1]
                    parsed = parse_email_message(raw_email)

                    thread_id = resolve_thread_id(
                        mailbox.id,
                        parsed['message_id'],
                        parsed['in_reply_to'],
                        parsed['references'],
                        parsed['subject'],
                    )

                    existing = EmailMessage.objects.filter(
                        mailbox=mailbox,
                        uid=uid_str,
                    ).first()

                    defaults = {
                        'subject': parsed['subject'],
                        'sender': parsed['sender'],
                        'body_text': parsed['body_text'],
                        'body_html': parsed['body_html'],
                        'message_id': parsed['message_id'],
                        'in_reply_to': parsed['in_reply_to'],
                        'references': parsed['references'],
                        'thread_id': thread_id,
                        'received_at': parsed['received_at'],
                    }

                    if not existing:
                        defaults.update({
                            'processed': False,
                            'category': '',
                            'ai_summary': '',
                            'ai_draft_reply': '',
                            'priority_score': None,
                        })

                    new_email, created = EmailMessage.objects.update_or_create(
                        mailbox=mailbox,
                        uid=uid_str,
                        defaults=defaults,
                    )

                    if created:
                        count += 1

                    if created or not existing or not existing.processed:
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
        include_hidden = request.query_params.get('include_hidden', '').lower() in (
            'true', '1', 'yes',
        )
        qs = _queryset_for_user(request, mailbox_id, include_hidden=include_hidden)

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

        fetch_limit = min(limit * 8, 2000)
        emails = list(qs.order_by('-received_at')[:fetch_limit])
        threads = collapse_to_latest_per_thread(emails)[:limit]
        serializer = EmailMessageSerializer(
            threads,
            many=True,
            context={
                'thread_counts': _thread_counts_for_emails(
                    threads,
                    include_hidden=include_hidden,
                ),
            },
        )
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
        parent = None
        reply_id = data.get('reply_to_email_id')
        if reply_id:
            parent = EmailMessage.objects.filter(
                id=reply_id,
                mailbox=mailbox,
            ).first()

        new_message_id = f'{uuid.uuid4()}@{mailbox.username.split("@")[-1]}'
        references_parts = []
        if parent:
            if parent.references:
                references_parts.extend(parse_references(parent.references))
            if parent.message_id:
                references_parts.append(parent.message_id)
        references_header = ' '.join(f'<{mid}>' for mid in references_parts if mid)

        msg = MIMEMultipart()
        msg['From'] = mailbox.username
        msg['To'] = data['to']
        msg['Subject'] = data['subject']
        msg['Message-ID'] = f'<{new_message_id}>'
        if parent and parent.message_id:
            msg['In-Reply-To'] = f'<{parent.message_id}>'
        if references_header:
            msg['References'] = references_header
        msg.attach(MIMEText(data['body'], 'plain'))

        try:
            host = mailbox.smtp_host
            port = mailbox.smtp_port

            server = smtplib.SMTP_SSL(host, port)
            server.login(mailbox.username, mailbox.password)
            server.send_message(msg)
            server.quit()

            thread_id = parent.thread_id if parent and parent.thread_id else f'mid:{new_message_id}'
            if parent and not parent.thread_id:
                parent.thread_id = thread_id
                parent.save(update_fields=['thread_id'])

            EmailMessage.objects.create(
                mailbox=mailbox,
                subject=data['subject'],
                sender=mailbox.username,
                body_text=data['body'],
                body_html='',
                uid=f'sent-{timezone.now().timestamp()}',
                message_id=new_message_id,
                in_reply_to=parent.message_id if parent else '',
                references=references_header,
                thread_id=thread_id,
                processed=True,
                processed_at=timezone.now(),
            )

            return Response({"status": "sent", "to": data['to']})

        except Exception as e:
            return Response(
                {"error": f"SMTP error: {str(e)}"},
                status=drf_status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EmailThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, email_id):
        email = _get_user_email(request, email_id)
        if not email:
            return Response(
                {"error": "Email not found"},
                status=drf_status.HTTP_404_NOT_FOUND,
            )

        include_hidden = request.query_params.get('include_hidden', '').lower() in (
            'true', '1', 'yes',
        )
        thread_emails = get_thread_messages(email, include_hidden=include_hidden)
        serializer = EmailMessageSerializer(thread_emails, many=True)
        return Response({
            "email_id": email.id,
            "thread_id": email.thread_id,
            "messages": serializer.data,
        })


class HideEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, email_id):
        email = _get_user_email(request, email_id)
        if not email:
            return Response({"error": "Email not found"}, status=drf_status.HTTP_404_NOT_FOUND)
        email.is_hidden = True
        email.save(update_fields=['is_hidden'])
        return Response({"status": "hidden", "email_id": email.id})


class UnhideEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, email_id):
        email = EmailMessage.objects.filter(
            id=email_id,
            mailbox__user=request.user,
        ).first()
        if not email:
            return Response({"error": "Email not found"}, status=drf_status.HTTP_404_NOT_FOUND)
        email.is_hidden = False
        email.save(update_fields=['is_hidden'])
        return Response({"status": "visible", "email_id": email.id})


class DeleteEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, email_id):
        email = _get_user_email(request, email_id)
        if not email:
            return Response({"error": "Email not found"}, status=drf_status.HTTP_404_NOT_FOUND)
        deleted_id = email.id
        email.delete()
        return Response({"status": "deleted", "email_id": deleted_id})


class HideThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, email_id):
        email = _get_user_email(request, email_id)
        if not email:
            return Response({"error": "Email not found"}, status=drf_status.HTTP_404_NOT_FOUND)

        if email.thread_id:
            updated = EmailMessage.objects.filter(
                mailbox=email.mailbox,
                thread_id=email.thread_id,
            ).update(is_hidden=True)
        else:
            email.is_hidden = True
            email.save(update_fields=['is_hidden'])
            updated = 1

        return Response({
            "status": "hidden",
            "thread_id": email.thread_id,
            "updated_count": updated,
        })


class UnhideThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, email_id):
        email = EmailMessage.objects.filter(
            id=email_id,
            mailbox__user=request.user,
        ).first()
        if not email:
            return Response({"error": "Email not found"}, status=drf_status.HTTP_404_NOT_FOUND)

        if email.thread_id:
            updated = EmailMessage.objects.filter(
                mailbox=email.mailbox,
                thread_id=email.thread_id,
            ).update(is_hidden=False)
        else:
            email.is_hidden = False
            email.save(update_fields=['is_hidden'])
            updated = 1

        return Response({
            "status": "visible",
            "thread_id": email.thread_id,
            "updated_count": updated,
        })


class DeleteThreadView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, email_id):
        email = _get_user_email(request, email_id)
        if not email:
            return Response({"error": "Email not found"}, status=drf_status.HTTP_404_NOT_FOUND)

        if email.thread_id:
            qs = EmailMessage.objects.filter(
                mailbox=email.mailbox,
                thread_id=email.thread_id,
            )
        else:
            qs = EmailMessage.objects.filter(pk=email.pk)

        deleted_count, _ = qs.delete()
        return Response({
            "status": "deleted",
            "thread_id": email.thread_id,
            "deleted_count": deleted_count,
        })


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

        thread_emails = get_thread_messages(email)

        if not thread_emails:
            return Response(
                {"error": "No emails found for this thread"},
                status=drf_status.HTTP_404_NOT_FOUND
            )

        conversation_text = ""
        for msg in thread_emails:
            conversation_text += (
                f"OD: {msg.sender}\n"
                f"TEMAT: {msg.subject}\n"
                f"TREŚĆ:\n{(msg.body_text or msg.body_html)[:1000]}\n\n"
                "----------\n\n"
            )

        from .tasks import query_ollama

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

        email.thread_summary = summary
        email.save(update_fields=['thread_summary'])

        return Response({
            "email_id": email.id,
            "subject": email.subject,
            "thread_summary": summary,
        })