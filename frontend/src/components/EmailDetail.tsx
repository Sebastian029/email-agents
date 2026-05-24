import { useCallback, useEffect, useState } from 'react'
import type { EmailMessage } from '../types'
import { categoryColor, categoryLabel } from '../lib/categories'
import { buildInitialReply, buildReplyBody } from '../lib/emailReply'
import * as emailsApi from '../api/emails'
import { ApiError } from '../api/client'

interface EmailDetailProps {
  email: EmailMessage | null
  showHidden?: boolean
  onSent?: () => void
  onRemoved?: () => void
}

export function EmailDetail({ email, showHidden = false, onSent, onRemoved }: EmailDetailProps) {
  const [actionLoading, setActionLoading] = useState(false)
  const [replyTo, setReplyTo] = useState('')
  const [replySubject, setReplySubject] = useState('')
  const [replyBody, setReplyBody] = useState('')
  const [sending, setSending] = useState(false)
  const [threadLoading, setThreadLoading] = useState(false)
  const [threadSummaryLoading, setThreadSummaryLoading] = useState(false)
  const [threadMessages, setThreadMessages] = useState<EmailMessage[]>([])
  const [threadSummary, setThreadSummary] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const applyReplyDefaults = useCallback((msg: EmailMessage, draftOnly = false) => {
    const initial = buildInitialReply(msg)
    setReplyTo(initial.to)
    setReplySubject(initial.subject)
    if (!draftOnly) {
      setReplyBody(initial.body)
    } else {
      setReplyBody(buildReplyBody(msg, msg.ai_draft_reply))
    }
  }, [])

  const loadThread = useCallback(async (msg: EmailMessage) => {
    setThreadLoading(true)
    setError(null)
    try {
      const res = await emailsApi.fetchEmailThread(msg.id, showHidden)
      setThreadMessages(res.messages)
    } catch (e) {
      setThreadMessages([msg])
      setError(e instanceof ApiError ? e.message : 'Błąd ładowania wątku')
    } finally {
      setThreadLoading(false)
    }
  }, [showHidden])

  useEffect(() => {
    if (!email) return
    setThreadSummary('')
    setError(null)
    setSuccess(null)
    applyReplyDefaults(email)
    loadThread(email)
  }, [email, applyReplyDefaults, loadThread])

  if (!email) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-zinc-500">
        <p className="text-sm">Wybierz wiadomość z listy</p>
      </div>
    )
  }

  const handleUseDraft = () => {
    applyReplyDefaults(email, true)
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
        reply_to_email_id: email.id,
      })
      setSuccess('Wiadomość wysłana.')
      onSent?.()
      await loadThread(email)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd wysyłki')
    } finally {
      setSending(false)
    }
  }

  const handleHideThread = async () => {
    if (!email || !window.confirm('Ukryć cały wątek?')) return
    setActionLoading(true)
    setError(null)
    try {
      await emailsApi.hideThread(email.id)
      onRemoved?.()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd ukrywania wątku')
    } finally {
      setActionLoading(false)
    }
  }

  const handleUnhideThread = async () => {
    if (!email) return
    setActionLoading(true)
    setError(null)
    try {
      await emailsApi.unhideThread(email.id)
      onRemoved?.()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd przywracania wątku')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDeleteThread = async () => {
    if (!email || !window.confirm('Trwale usunąć cały wątek? Tej operacji nie można cofnąć.')) return
    setActionLoading(true)
    setError(null)
    try {
      await emailsApi.deleteThread(email.id)
      onRemoved?.()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd usuwania wątku')
    } finally {
      setActionLoading(false)
    }
  }

  const handleHideMessage = async (msg: EmailMessage) => {
    if (!window.confirm('Ukryć tę wiadomość?')) return
    setActionLoading(true)
    setError(null)
    try {
      await emailsApi.hideEmail(msg.id)
      if (msg.id === email?.id) {
        onRemoved?.()
      } else {
        await loadThread(email!)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd ukrywania wiadomości')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDeleteMessage = async (msg: EmailMessage) => {
    if (!window.confirm('Trwale usunąć tę wiadomość?')) return
    setActionLoading(true)
    setError(null)
    try {
      await emailsApi.deleteEmail(msg.id)
      const remaining = threadMessages.filter((m) => m.id !== msg.id)
      if (msg.id === email?.id || remaining.length === 0) {
        onRemoved?.()
      } else {
        await loadThread(email!)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd usuwania wiadomości')
    } finally {
      setActionLoading(false)
    }
  }

  const handleThreadSummary = async () => {
    setThreadSummaryLoading(true)
    setError(null)
    try {
      const res = await emailsApi.fetchThreadSummary(email.id)
      setThreadSummary(res.thread_summary)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd podsumowania wątku')
    } finally {
      setThreadSummaryLoading(false)
    }
  }

  const displayThread = threadSummary || email.thread_summary
  const history =
    threadMessages.length > 0 ? threadMessages : [email]
  const showConversation = history.length > 1

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
          {history.length > 1 && (
            <span className="rounded-full bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-400">
              {history.length} wiadomości
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
        <div className="mt-3 flex flex-wrap gap-2">
          {showHidden ? (
            <button
              type="button"
              disabled={actionLoading}
              onClick={handleUnhideThread}
              className="rounded-lg border border-zinc-600 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
            >
              Przywróć wątek
            </button>
          ) : (
            <button
              type="button"
              disabled={actionLoading}
              onClick={handleHideThread}
              className="rounded-lg border border-zinc-600 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-800 disabled:opacity-50"
            >
              Ukryj wątek
            </button>
          )}
          <button
            type="button"
            disabled={actionLoading}
            onClick={handleDeleteThread}
            className="rounded-lg border border-rose-900/50 px-3 py-1.5 text-xs text-rose-400 transition hover:bg-rose-950/40 disabled:opacity-50"
          >
            Usuń wątek
          </button>
        </div>
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
                Wstaw propozycję
              </button>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
              {email.ai_draft_reply}
            </p>
          </section>
        )}

        <section>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            {showConversation ? 'Historia rozmowy' : 'Treść'}
          </h3>
          {threadLoading && history.length <= 1 ? (
            <p className="text-sm text-zinc-500">Ładowanie historii…</p>
          ) : (
            <div className="space-y-3">
              {history.map((msg) => {
                const isCurrent = msg.id === email.id
                return (
                  <article
                    key={msg.id}
                    className={`rounded-xl border p-4 ${
                      isCurrent
                        ? 'border-zinc-600/80 bg-zinc-900/50'
                        : 'border-zinc-800/60 bg-zinc-900/30'
                    }`}
                  >
                    <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                      <p className="text-sm font-medium text-zinc-300">
                        {msg.sender}
                      </p>
                      <div className="flex items-center gap-2">
                        {showConversation && (
                          <>
                            {!showHidden && (
                              <button
                                type="button"
                                disabled={actionLoading}
                                onClick={() => handleHideMessage(msg)}
                                className="text-[10px] text-zinc-500 hover:text-zinc-300"
                              >
                                Ukryj
                              </button>
                            )}
                            <button
                              type="button"
                              disabled={actionLoading}
                              onClick={() => handleDeleteMessage(msg)}
                              className="text-[10px] text-rose-500/80 hover:text-rose-400"
                            >
                              Usuń
                            </button>
                          </>
                        )}
                        <time className="text-xs text-zinc-600">
                          {new Date(msg.received_at).toLocaleString('pl-PL')}
                        </time>
                      </div>
                    </div>
                    {msg.subject !== email.subject && (
                      <p className="mb-2 text-xs text-zinc-500">{msg.subject}</p>
                    )}
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-400">
                      {msg.body_text || '(brak treści tekstowej)'}
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>

        <section className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Podsumowanie wątku (AI)
            </h3>
            <button
              type="button"
              onClick={handleThreadSummary}
              disabled={threadSummaryLoading}
              className="rounded-lg bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 transition hover:bg-zinc-700 disabled:opacity-50"
            >
              {threadSummaryLoading ? 'Generuję…' : 'Generuj'}
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
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Odpowiedz
          </h3>
          <p className="mb-3 text-xs text-zinc-600">
            Pola wypełniane automatycznie — cytat oryginału jest już w treści.
          </p>
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
              rows={10}
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
