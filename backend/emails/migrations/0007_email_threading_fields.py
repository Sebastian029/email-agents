from django.db import migrations, models


def backfill_thread_ids(apps, schema_editor):
    EmailMessage = apps.get_model('emails', 'EmailMessage')

    def normalize_subject(subject):
        s = (subject or '').strip()
        prefixes = ('re:', 'fw:', 'fwd:', 'odp:')
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if s.lower().startswith(prefix):
                    s = s[len(prefix):].strip()
                    changed = True
        return s.lower()

    for email in EmailMessage.objects.all().iterator():
        if email.thread_id:
            continue
        key = f'subject:{email.mailbox_id}:{normalize_subject(email.subject)}'
        email.thread_id = key
        email.save(update_fields=['thread_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0006_emailmessage_thread_summary'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailmessage',
            name='sender',
            field=models.CharField(max_length=500),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='message_id',
            field=models.CharField(blank=True, db_index=True, max_length=500),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='in_reply_to',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='references',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='emailmessage',
            name='thread_id',
            field=models.CharField(blank=True, db_index=True, max_length=500),
        ),
        migrations.RunPython(backfill_thread_ids, migrations.RunPython.noop),
    ]
