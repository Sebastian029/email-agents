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
    mailbox = serializers.PrimaryKeyRelatedField(read_only=True)
    thread_message_count = serializers.SerializerMethodField()

    class Meta:
        model = EmailMessage
        fields = [
            'id',
            'mailbox',
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
            'thread_id',
            'thread_message_count',
        ]

    def get_thread_message_count(self, obj):
        counts = self.context.get('thread_counts')
        if counts is not None:
            if obj.thread_id:
                return counts.get(obj.thread_id, 1)
            return 1
        qs = EmailMessage.objects.filter(mailbox=obj.mailbox)
        if obj.thread_id:
            qs = qs.filter(thread_id=obj.thread_id)
        else:
            qs = qs.filter(pk=obj.pk)
        if not self.context.get('include_hidden'):
            qs = qs.filter(is_hidden=False)
        return qs.count()


class SendEmailSerializer(serializers.Serializer):
    mailbox = serializers.PrimaryKeyRelatedField(queryset=Mailbox.objects.all())
    to = serializers.EmailField()
    subject = serializers.CharField(max_length=500)
    body = serializers.CharField()
    reply_to_email_id = serializers.IntegerField(required=False, allow_null=True)
