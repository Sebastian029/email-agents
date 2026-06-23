from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from .models import Mailbox, EmailMessage
from .threading import normalize_subject, resolve_thread_id, collapse_to_latest_per_thread

User = get_user_model()



class MailboxModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass1234')

    def test_mailbox_creation(self):
        mb = Mailbox.objects.create(
            user=self.user,
            name='Prywatna',
            username='test@example.com',
            password='secret',
            imap_host='imap.example.com',
            smtp_host='smtp.example.com',
        )
        self.assertEqual(mb.user, self.user)
        self.assertEqual(mb.name, 'Prywatna')
        self.assertEqual(mb.imap_port, 993)
        self.assertEqual(mb.smtp_port, 587)

    def test_mailbox_unique_together(self):
        Mailbox.objects.create(
            user=self.user, name='A', username='dup@example.com',
            password='x', imap_host='imap.x.com', smtp_host='smtp.x.com',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Mailbox.objects.create(
                user=self.user, name='B', username='dup@example.com',
                password='x', imap_host='imap.x.com', smtp_host='smtp.x.com',
            )

    def test_email_message_creation(self):
        mb = Mailbox.objects.create(
            user=self.user, name='T', username='t@example.com',
            password='x', imap_host='imap.x.com', smtp_host='smtp.x.com',
        )
        email = EmailMessage.objects.create(
            mailbox=mb, subject='Testowy temat', sender='ktos@example.com',
            body_text='Treść wiadomości.', uid='uid-001',
        )
        self.assertFalse(email.processed)
        self.assertIsNone(email.priority_score)
        self.assertEqual(email.category, '')
        self.assertEqual(email.ai_summary, '')



class ThreadingTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='threaduser', password='pass1234')
        self.mb = Mailbox.objects.create(
            user=self.user, name='T', username='t@thread.com',
            password='x', imap_host='imap.x.com', smtp_host='smtp.x.com',
        )

    def test_normalize_subject_removes_re_prefix(self):
        self.assertEqual(normalize_subject('Re: Spotkanie jutro'), 'spotkanie jutro')
        self.assertEqual(normalize_subject('FW: Faktura'), 'faktura')
        self.assertEqual(normalize_subject('Odp: Pytanie'), 'pytanie')

    def test_normalize_subject_nested_prefixes(self):
        self.assertEqual(normalize_subject('Re: Re: Temat'), 'temat')

    def test_resolve_thread_id_by_message_id(self):
        thread_id = resolve_thread_id(
            self.mb.id, '<msg1@example.com>', '', '', 'Temat'
        )
        self.assertEqual(thread_id, 'mid:<msg1@example.com>')

    def test_resolve_thread_id_inherits_parent(self):
        parent = EmailMessage.objects.create(
            mailbox=self.mb, subject='Temat', sender='a@x.com',
            body_text='Treść', uid='uid-p1',
            message_id='<parent@example.com>',
            thread_id='mid:<parent@example.com>',
        )
        child_thread_id = resolve_thread_id(
            self.mb.id, '<child@example.com>', '<parent@example.com>', '', 'Re: Temat'
        )
        self.assertEqual(child_thread_id, parent.thread_id)

    def test_collapse_to_latest_per_thread(self):
        for i in range(3):
            EmailMessage.objects.create(
                mailbox=self.mb, subject='Temat', sender='a@x.com',
                body_text='Treść', uid=f'uid-c{i}',
                thread_id='tid-shared',
            )
        qs = list(EmailMessage.objects.filter(mailbox=self.mb))
        collapsed = collapse_to_latest_per_thread(qs)
        self.assertEqual(len(collapsed), 1)


class MailboxAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='apiuser', password='pass1234')
        self.client.force_authenticate(user=self.user)

    def test_create_mailbox(self):
        data = {
            'name': 'Praca', 'username': 'praca@example.com', 'password': 'secret',
            'imap_host': 'imap.example.com', 'imap_port': 993,
            'smtp_host': 'smtp.example.com', 'smtp_port': 587,
        }
        response = self.client.post('/api/emails/mailboxes/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Mailbox.objects.filter(user=self.user).count(), 1)

    def test_list_mailboxes(self):
        Mailbox.objects.create(
            user=self.user, name='M', username='m@x.com',
            password='x', imap_host='imap.x.com', smtp_host='smtp.x.com',
        )
        response = self.client.get('/api/emails/mailboxes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_unauthenticated_access_denied(self):
        unauth = APIClient()
        response = unauth.get('/api/emails/mailboxes/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_duplicate_mailbox_username_rejected(self):
        data = {
            'name': 'A', 'username': 'dup@example.com', 'password': 'x',
            'imap_host': 'imap.x.com', 'imap_port': 993,
            'smtp_host': 'smtp.x.com', 'smtp_port': 587,
        }
        self.client.post('/api/emails/mailboxes/', data, format='json')
        response = self.client.post('/api/emails/mailboxes/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='emailuser', password='pass1234')
        self.client.force_authenticate(user=self.user)
        self.mb = Mailbox.objects.create(
            user=self.user, name='Test', username='t@test.com',
            password='x', imap_host='imap.x.com', smtp_host='smtp.x.com',
        )

    def _create_email(self, uid='uid-1', subject='Temat', category='', hidden=False):
        return EmailMessage.objects.create(
            mailbox=self.mb, subject=subject, sender='a@x.com',
            body_text='Treść', uid=uid, category=category, is_hidden=hidden,
        )

    def test_list_emails_returns_200(self):
        response = self.client.get('/api/emails/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_emails_excludes_hidden_by_default(self):
        self._create_email(uid='uid-v', hidden=False)
        self._create_email(uid='uid-h', hidden=True)
        response = self.client.get('/api/emails/list/')
        ids = [e['id'] for e in response.data]
        hidden_email = EmailMessage.objects.get(uid='uid-h')
        self.assertNotIn(hidden_email.id, ids)

    def test_hide_email(self):
        email = self._create_email(uid='uid-hide')
        response = self.client.post(f'/api/emails/{email.id}/hide/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        email.refresh_from_db()
        self.assertTrue(email.is_hidden)

    def test_delete_email(self):
        email = self._create_email(uid='uid-del')
        response = self.client.delete(f'/api/emails/{email.id}/delete/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(EmailMessage.objects.filter(id=email.id).exists())

    def test_filter_emails_by_category(self):
        self._create_email(uid='uid-g', category='comp.graphics')
        self._create_email(uid='uid-e', category='sci.electronics')
        response = self.client.get('/api/emails/list/?category=comp.graphics')
        categories = [e['category'] for e in response.data]
        self.assertTrue(all(c == 'comp.graphics' for c in categories))

