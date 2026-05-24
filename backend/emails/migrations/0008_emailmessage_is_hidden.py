from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0007_email_threading_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailmessage',
            name='is_hidden',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
