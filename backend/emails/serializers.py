from rest_framework import serializers
from .models import EmailMessage, Mailbox


class MailboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mailbox
        fields = ['id', 'user', 'name', 'username', 'imap_host', 'imap_port', 'smtp_host', 'smtp_port']
        read_only_fields = ['id', 'user']

class CreateMailboxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mailbox
        fields = ['name', 'username', 'password', 'imap_host', 'imap_port', 'smtp_host', 'smtp_port']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_username(self, value):
        request = self.context.get('request')
        if request is None or request.user.is_anonymous:
            return value
        user = request.user
        if Mailbox.objects.filter(user=user, username=value).exists():
            raise serializers.ValidationError("Mailbox with this username already exists")
        return value

class EmailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        fields = [
            'id',
            'subject',
            'sender',
            'body_text',
            'received_at',
            'processed',
            'category',
            'priority_score',
            'ai_summary',
            'ai_draft_reply',
            'thread_summary',
        ]

class SendEmailSerializer(serializers.Serializer):
    mailbox = serializers.PrimaryKeyRelatedField(queryset=Mailbox.objects.all())
    to = serializers.EmailField()
    subject = serializers.CharField(max_length=200)
    body = serializers.CharField()
