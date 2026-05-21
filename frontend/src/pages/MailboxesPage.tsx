import { useEffect, useState, type FormEvent } from 'react'
import type { CreateMailboxPayload, Mailbox } from '../types'
import * as emailsApi from '../api/emails'
import { ApiError } from '../api/client'

const defaultForm: CreateMailboxPayload = {
  name: 'Główna',
  username: '',
  password: '',
  imap_host: 'imap.wp.pl',
  imap_port: 993,
  smtp_host: 'smtp.wp.pl',
  smtp_port: 587,
}

export function MailboxesPage() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([])
  const [form, setForm] = useState<CreateMailboxPayload>(defaultForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      setMailboxes(await emailsApi.fetchMailboxes())
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd ładowania')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      await emailsApi.createMailbox(form)
      setSuccess('Skrzynka dodana.')
      setForm({ ...defaultForm, name: form.name })
      await load()
    } catch (err) {
      if (err instanceof ApiError && err.data) {
        const data = err.data as Record<string, string[] | string>
        const parts = Object.entries(data).map(([k, v]) =>
          Array.isArray(v) ? `${k}: ${v.join(', ')}` : `${k}: ${v}`,
        )
        setError(parts.join(' · ') || err.message)
      } else {
        setError('Nie udało się dodać skrzynki')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Usunąć tę skrzynkę i powiązane wiadomości?')) return
    try {
      await emailsApi.deleteMailbox(id)
      await load()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Błąd usuwania')
    }
  }

  const field = (
    key: keyof CreateMailboxPayload,
    label: string,
    type: string = 'text',
  ) => (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-zinc-500">
        {label}
      </label>
      <input
        type={type}
        required={key !== 'smtp_host'}
        value={String(form[key])}
        onChange={(e) =>
          setForm((f) => ({
            ...f,
            [key]:
              key === 'imap_port' || key === 'smtp_port'
                ? Number(e.target.value)
                : e.target.value,
          }))
        }
        className="w-full rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
      />
    </div>
  )

  return (
    <div className="overflow-y-auto px-6 py-6">
      <h2 className="text-lg font-semibold text-white">Skrzynki pocztowe</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Połącz konto IMAP/SMTP — dane logowania są przechowywane w bazie
        backendu.
      </p>

      <section className="mt-8">
        <h3 className="text-sm font-medium text-zinc-400">Twoje skrzynki</h3>
        {loading ? (
          <p className="mt-4 text-sm text-zinc-500">Ładowanie…</p>
        ) : mailboxes.length === 0 ? (
          <p className="mt-4 text-sm text-zinc-500">Brak skrzynek — dodaj pierwszą poniżej.</p>
        ) : (
          <ul className="mt-4 space-y-2">
            {mailboxes.map((mb) => (
              <li
                key={mb.id}
                className="flex items-center justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/30 px-4 py-3"
              >
                <div>
                  <p className="font-medium text-zinc-200">{mb.name}</p>
                  <p className="text-sm text-zinc-500">{mb.username}</p>
                  <p className="text-xs text-zinc-600">
                    IMAP {mb.imap_host}:{mb.imap_port} · SMTP {mb.smtp_host}:
                    {mb.smtp_port}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(mb.id)}
                  className="rounded-lg border border-rose-900/50 px-3 py-1.5 text-xs text-rose-400 transition hover:bg-rose-950/30"
                >
                  Usuń
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-10 max-w-xl">
        <h3 className="text-sm font-medium text-zinc-400">Dodaj skrzynkę</h3>
        <form onSubmit={handleSubmit} className="mt-4 grid gap-4 sm:grid-cols-2">
          {field('name', 'Nazwa (np. Główna)')}
          {field('username', 'Adres e-mail / login')}
          {field('password', 'Hasło', 'password')}
          {field('imap_host', 'Serwer IMAP')}
          {field('imap_port', 'Port IMAP', 'number')}
          {field('smtp_host', 'Serwer SMTP')}
          {field('smtp_port', 'Port SMTP', 'number')}

          <div className="sm:col-span-2">
            {error && (
              <p className="mb-3 rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-400">
                {error}
              </p>
            )}
            {success && (
              <p className="mb-3 rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
                {success}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-zinc-100 px-5 py-2 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:opacity-50"
            >
              {submitting ? 'Zapisywanie…' : 'Dodaj skrzynkę'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
