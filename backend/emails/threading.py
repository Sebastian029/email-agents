import re
from email.utils import parseaddr, parsedate_to_datetime

from django.utils import timezone

from .models import EmailMessage

RE_PREFIXES = ('re:', 'fw:', 'fwd:', 'odp:')


def normalize_subject(subject: str) -> str:
    s = (subject or '').strip()
    changed = True
    while changed:
        changed = False
        for prefix in RE_PREFIXES:
            if s.lower().startswith(prefix):
                s = s[len(prefix):].strip()
                changed = True
    return s.lower()


def extract_message_id(value: str) -> str:
    if not value:
        return ''
    match = re.search(r'<([^>]+)>', value)
    if match:
        return match.group(1).strip()
    return value.strip().strip('<>')


def parse_references(value: str) -> list[str]:
    if not value:
        return []
    return [extract_message_id(part) for part in re.findall(r'<[^>]+>', value)]


def parse_sender_address(sender: str) -> str:
    _, addr = parseaddr(sender or '')
    return addr or (sender or '').strip()


def subject_thread_key(mailbox_id: int, subject: str) -> str:
    return f'subject:{mailbox_id}:{normalize_subject(subject)}'


def resolve_thread_id(
    mailbox_id: int,
    message_id: str,
    in_reply_to: str,
    references: str,
    subject: str,
) -> str:
    parent_ids = []
    if in_reply_to:
        parent_ids.append(in_reply_to)
    parent_ids.extend(parse_references(references))

    for parent_id in reversed(parent_ids):
        if not parent_id:
            continue
        parent = EmailMessage.objects.filter(
            mailbox_id=mailbox_id,
            message_id=parent_id,
        ).first()
        if parent and parent.thread_id:
            return parent.thread_id

    if message_id:
        return f'mid:{message_id}'

    return subject_thread_key(mailbox_id, subject)


def thread_key(email: EmailMessage) -> str:
    return email.thread_id or f'single-{email.id}'


def get_thread_messages(email: EmailMessage, include_hidden: bool = False):
    if email.thread_id:
        qs = EmailMessage.objects.filter(
            mailbox=email.mailbox,
            thread_id=email.thread_id,
        )
        if not include_hidden:
            qs = qs.filter(is_hidden=False)
        return list(qs.order_by('received_at'))

    base = normalize_subject(email.subject)
    qs = EmailMessage.objects.filter(mailbox=email.mailbox)
    messages = [
        m for m in qs
        if normalize_subject(m.subject) == base
        and (include_hidden or not m.is_hidden)
    ]
    return sorted(messages, key=lambda m: m.received_at)


def collapse_to_latest_per_thread(emails):
    seen = {}
    for email in emails:
        key = thread_key(email)
        if key not in seen:
            seen[key] = email
    return list(seen.values())


def parse_email_date(msg) -> timezone.datetime:
    date_header = msg.get('Date')
    if not date_header:
        return timezone.now()
    try:
        dt = parsedate_to_datetime(date_header)
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone=timezone.utc)
        return dt
    except (TypeError, ValueError, OverflowError):
        return timezone.now()
