import { useState } from 'react'
import type { EmailMessage } from '../types'
import { categoryColor, categoryLabel } from '../lib/categories'
import * as emailsApi from '../api/emails'
import { ApiError } from '../api/client'

interface EmailDetailProps {
  email: EmailMessage | null
  onSent?: () => void
}

export function EmailDetail({ email, onSent }: EmailDetailProps) {
  const [replyTo, setReplyTo] = useState('')
  const [replySubject, setReplySubject] = useState('')
  const [replyBody, setReplyBody] = useState('')
  const [sending, setSending] = useState(false)
  const [threadLoading, setThreadLoading] = useState(false)
  const [threadSummary, setThreadSummary] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  if (!email) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-zinc-500">
        <p className="text-sm">Wybierz wiadomość z listy</p>
      </div>
    )
  }

  const handleUseDraft = () => {
    setReplyTo(email.sender.replace(/<.*>/, '').trim() || email.sender)
    setReplySubject(
      email.subject.startsWith('Re:') ? email.subject : `Re: ${email.subject}`,
    )
    setReplyBody(email.ai_draft_reply || '')
  }

  const handleSend = async () => {
    if (!replyTo || !replySubject || !replyBody) return
    setSending(true)
    setError(null)
    setSuccess(null)
    try {
      await emailsApi.sendEmail({
        mailbox: email.mailbox,
        to: replyTo,
        subject: replySubject,
        body: replyBody,
      })
      setSuccess('Wiadomość wysłana.')
      onSent?.()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd wysyłki')
    } finally {
      setSending(false)
    }
  }

  const handleThreadSummary = async () => {
    setThreadLoading(true)
    setError(null)
    try {
      const res = await emailsApi.fetchThreadSummary(email.id)
      setThreadSummary(res.thread_summary)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd podsumowania wątku')
    } finally {
      setThreadLoading(false)
    }
  }

  const displayThread = threadSummary || email.thread_summary

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="border-b border-zinc-800/80 px-6 py-4">
        <div className="flex flex-wrap items-start gap-2">
          <h2 className="flex-1 text-lg font-semibold text-white">
            {email.subject || '(bez tematu)'}
          </h2>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${categoryColor(email.category)}`}
          >
            {categoryLabel(email.category)}
          </span>
          {email.priority_score != null && (
            <span className="rounded-full bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-400">
              Priorytet {email.priority_score}/10
            </span>
          )}
          {!email.processed && (
            <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs text-amber-300">
              Przetwarzanie AI…
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-zinc-500">
          Od: <span className="text-zinc-400">{email.sender}</span>
          {' · '}
          {new Date(email.received_at).toLocaleString('pl-PL')}
        </p>
      </header>

      <div className="flex-1 space-y-6 overflow-y-auto px-6 py-5">
        {email.ai_summary && (
          <section className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Streszczenie AI
            </h3>
            <p className="text-sm leading-relaxed text-zinc-300">
              {email.ai_summary}
            </p>
          </section>
        )}

        {email.ai_draft_reply && (
          <section className="rounded-xl border border-sky-900/40 bg-sky-950/20 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-sky-400/80">
                Propozycja odpowiedzi
              </h3>
              <button
                type="button"
                onClick={handleUseDraft}
                className="text-xs text-sky-400 hover:text-sky-300"
              >
                Użyj w odpowiedzi
              </button>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
              {email.ai_draft_reply}
            </p>
          </section>
        )}

        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Treść
          </h3>
          <div className="whitespace-pre-wrap rounded-xl border border-zinc-800/60 bg-zinc-900/30 p-4 text-sm leading-relaxed text-zinc-400">
            {email.body_text || '(brak treści tekstowej)'}
          </div>
        </section>

        <section className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Podsumowanie wątku
            </h3>
            <button
              type="button"
              onClick={handleThreadSummary}
              disabled={threadLoading}
              className="rounded-lg bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-700 disabled:opacity-50"
            >
              {threadLoading ? 'Generuję…' : 'Generuj'}
            </button>
          </div>
          {displayThread ? (
            <p className="text-sm leading-relaxed text-zinc-300">
              {displayThread}
            </p>
          ) : (
            <p className="text-sm text-zinc-600">
              Brak podsumowania — kliknij Generuj, aby stworzyć streszczenie
              całej rozmowy.
            </p>
          )}
        </section>

        <section className="rounded-xl border border-zinc-800/80 bg-[#13161c] p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Odpowiedz
          </h3>
          <div className="space-y-3">
            <input
              type="email"
              placeholder="Do"
              value={replyTo}
              onChange={(e) => setReplyTo(e.target.value)}
              className="w-full rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-zinc-500"
            />
            <input
              type="text"
              placeholder="Temat"
              value={replySubject}
              onChange={(e) => setReplySubject(e.target.value)}
              className="w-full rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-zinc-500"
            />
            <textarea
              rows={6}
              placeholder="Treść wiadomości"
              value={replyBody}
              onChange={(e) => setReplyBody(e.target.value)}
              className="w-full resize-y rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-zinc-500"
            />
            {error && <p className="text-sm text-rose-400">{error}</p>}
            {success && <p className="text-sm text-emerald-400">{success}</p>}
            <button
              type="button"
              onClick={handleSend}
              disabled={sending}
              className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:opacity-50"
            >
              {sending ? 'Wysyłanie…' : 'Wyślij'}
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
