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
    sender = models.EmailField()
    body_text = models.TextField()
    body_html = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    uid = models.CharField(max_length=100, unique=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
