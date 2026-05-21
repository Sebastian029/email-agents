import { useCallback, useEffect, useMemo, useState } from 'react'
import type { EmailCategory, EmailMessage, Mailbox } from '../types'
import { CATEGORIES, categoryColor, categoryLabel } from '../lib/categories'
import * as emailsApi from '../api/emails'
import { EmailDetail } from '../components/EmailDetail'
import { ApiError } from '../api/client'

export function InboxPage() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([])
  const [emails, setEmails] = useState<EmailMessage[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [mailboxFilter, setMailboxFilter] = useState<number | 'all'>('all')
  const [categoryFilter, setCategoryFilter] = useState<EmailCategory | 'all'>(
    'all',
  )
  const [loading, setLoading] = useState(true)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fetchMsg, setFetchMsg] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [mbList, emailList] = await Promise.all([
        emailsApi.fetchMailboxes(),
        emailsApi.listEmails({
          mailboxId: mailboxFilter === 'all' ? undefined : mailboxFilter,
        }),
      ])
      setMailboxes(mbList)
      setEmails(emailList)
      if (emailList.length) {
        setSelectedId((prev) =>
          prev && emailList.some((e) => e.id === prev) ? prev : emailList[0].id,
        )
      } else {
        setSelectedId(null)
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd ładowania')
    } finally {
      setLoading(false)
    }
  }, [mailboxFilter])

  const loadEmails = useCallback(async () => {
    try {
      const emailList = await emailsApi.listEmails({
        mailboxId: mailboxFilter === 'all' ? undefined : mailboxFilter,
      })
      setEmails(emailList)
      setSelectedId((prev) => {
        if (prev && emailList.some((e) => e.id === prev)) return prev
        return emailList[0]?.id ?? null
      })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd ładowania maili')
    }
  }, [mailboxFilter])

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    if (!loading) loadEmails()
  }, [mailboxFilter, loading, loadEmails])

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: emails.length }
    for (const cat of CATEGORIES) {
      counts[cat.id] = emails.filter((e) => e.category === cat.id).length
    }
    counts[''] = emails.filter((e) => !e.category).length
    return counts
  }, [emails])

  const filteredEmails = useMemo(() => {
    let list = emails
    if (mailboxFilter !== 'all') {
      list = list.filter((e) => e.mailbox === mailboxFilter)
    }
    if (categoryFilter !== 'all') {
      list = list.filter((e) => e.category === categoryFilter)
    }
    return list
  }, [emails, mailboxFilter, categoryFilter])

  const selected = filteredEmails.find((e) => e.id === selectedId) ?? null

  const handleFetch = async () => {
    if (!mailboxes.length) {
      setError('Dodaj najpierw skrzynkę pocztową w ustawieniach.')
      return
    }
    setFetching(true)
    setFetchMsg(null)
    setError(null)
    try {
      const res = await emailsApi.fetchEmailsFromServer()
      setFetchMsg(
        `Pobrano ${res.total_new_emails} wiadomości. AI klasyfikuje w tle — odśwież za chwilę.`,
      )
      await loadEmails()
      const poll = setInterval(loadEmails, 4000)
      setTimeout(() => clearInterval(poll), 60000)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd pobierania')
    } finally {
      setFetching(false)
    }
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-zinc-800/80 px-6 py-4">
        <h2 className="text-lg font-semibold text-white">Skrzynka odbiorcza</h2>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            value={mailboxFilter === 'all' ? 'all' : String(mailboxFilter)}
            onChange={(e) =>
              setMailboxFilter(
                e.target.value === 'all' ? 'all' : Number(e.target.value),
              )
            }
            className="rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-1.5 text-sm text-zinc-300 outline-none"
          >
            <option value="all">Wszystkie skrzynki</option>
            {mailboxes.map((mb) => (
              <option key={mb.id} value={mb.id}>
                {mb.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleFetch}
            disabled={fetching}
            className="rounded-lg bg-zinc-100 px-4 py-1.5 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:opacity-50"
          >
            {fetching ? 'Pobieranie…' : 'Pobierz z IMAP'}
          </button>
          <button
            type="button"
            onClick={loadEmails}
            className="rounded-lg border border-zinc-700/80 px-3 py-1.5 text-sm text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-200"
          >
            Odśwież
          </button>
        </div>
      </header>

      {(error || fetchMsg) && (
        <div className="px-6 pt-3">
          {error && (
            <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-400">
              {error}
            </p>
          )}
          {fetchMsg && (
            <p className="mt-2 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
              {fetchMsg}
            </p>
          )}
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        <div className="flex w-80 shrink-0 flex-col border-r border-zinc-800/80">
          <div className="flex gap-1 overflow-x-auto border-b border-zinc-800/80 px-2 py-2">
            <CategoryTab
              active={categoryFilter === 'all'}
              label="Wszystkie"
              count={categoryCounts.all ?? 0}
              onClick={() => setCategoryFilter('all')}
            />
            {CATEGORIES.map((cat) => (
              <CategoryTab
                key={cat.id}
                active={categoryFilter === cat.id}
                label={cat.label}
                count={
                  emails.filter((e) => e.category === cat.id).length
                }
                onClick={() => setCategoryFilter(cat.id)}
              />
            ))}
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <p className="p-4 text-sm text-zinc-500">Ładowanie…</p>
            ) : filteredEmails.length === 0 ? (
              <p className="p-4 text-sm text-zinc-500">
                Brak wiadomości w tej kategorii.
              </p>
            ) : (
              <ul>
                {filteredEmails.map((email) => (
                  <li key={email.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(email.id)}
                      className={`w-full border-b border-zinc-800/50 px-4 py-3 text-left transition ${
                        selectedId === email.id
                          ? 'bg-zinc-800/60'
                          : 'hover:bg-zinc-800/30'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="line-clamp-1 text-sm font-medium text-zinc-200">
                          {email.subject || '(bez tematu)'}
                        </span>
                        {!email.processed && (
                          <span className="h-2 w-2 shrink-0 rounded-full bg-amber-400" title="Przetwarzanie" />
                        )}
                      </div>
                      <p className="mt-0.5 line-clamp-1 text-xs text-zinc-500">
                        {email.sender}
                      </p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${categoryColor(email.category)}`}
                        >
                          {categoryLabel(email.category)}
                        </span>
                        <span className="text-[10px] text-zinc-600">
                          {new Date(email.received_at).toLocaleDateString(
                            'pl-PL',
                          )}
                        </span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <EmailDetail email={selected} onSent={loadEmails} />
        </div>
      </div>
    </div>
  )
}

function CategoryTab({
  active,
  label,
  count,
  onClick,
}: {
  active: boolean
  label: string
  count: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium transition ${
        active
          ? 'bg-zinc-700 text-white'
          : 'text-zinc-500 hover:bg-zinc-800/60 hover:text-zinc-300'
      }`}
    >
      {label}
      {count > 0 && (
        <span className="ml-1 text-zinc-600">({count})</span>
      )}
    </button>
  )
}
