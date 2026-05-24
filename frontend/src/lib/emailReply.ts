import type { EmailMessage } from '../types'

export function parseSenderAddress(sender: string): string {
  const match = sender.match(/<([^>]+)>/)
  if (match) return match[1].trim()
  const trimmed = sender.trim()
  if (trimmed.includes('@') && !trimmed.includes(' ')) return trimmed
  return trimmed
}

export function replySubject(subject: string): string {
  const s = subject || ''
  if (/^re:\s/i.test(s)) return s
  return `Re: ${s}`
}

export function quoteBody(email: EmailMessage): string {
  const date = new Date(email.received_at).toLocaleString('pl-PL')
  const text = (email.body_text || '').trim()
  if (!text) return ''
  const quoted = text
    .split('\n')
    .map((line) => `> ${line}`)
    .join('\n')
  return `\n\n---\nW dniu ${date}, ${email.sender} napisał(a):\n${quoted}`
}

export function buildReplyBody(
  email: EmailMessage,
  draft?: string,
): string {
  const main = (draft || email.ai_draft_reply || '').trim()
  const quote = quoteBody(email)
  if (main && quote) return `${main}${quote}`
  if (main) return main
  return quote.trimStart()
}

export function buildInitialReply(email: EmailMessage) {
  return {
    to: parseSenderAddress(email.sender),
    subject: replySubject(email.subject),
    body: buildReplyBody(email),
  }
}
