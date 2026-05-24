from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Mailbox(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    username = models.CharField(max_length=200)
    password = models.CharField(max_length=200)
    imap_host = models.CharField(max_length=200)
    imap_port = models.IntegerField(default=993)
    smtp_host = models.CharField(max_length=200, default='smtp.wp.pl')
    smtp_port = models.IntegerField(default=587)

    class Meta:
        unique_together = ['user', 'username']

class EmailMessage(models.Model):
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE)
    subject = models.TextField()
    sender = models.CharField(max_length=500)
    body_text = models.TextField()
    body_html = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    uid = models.CharField(max_length=100)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    message_id = models.CharField(max_length=500, blank=True, db_index=True)
    in_reply_to = models.CharField(max_length=500, blank=True)
    references = models.TextField(blank=True)
    thread_id = models.CharField(max_length=500, blank=True, db_index=True)

    category = models.CharField(max_length=100, blank=True)
    priority_score = models.IntegerField(null=True, blank=True)
    ai_summary = models.TextField(blank=True)
    ai_draft_reply = models.TextField(blank=True)

    thread_summary = models.TextField(blank=True)

    is_hidden = models.BooleanField(default=False, db_index=True)

    class Meta:
        unique_together = ['mailbox', 'uid']