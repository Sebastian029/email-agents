import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { ApiError } from '../api/client'

export function RegisterPage() {
  const { register, isAuthenticated, loading } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!loading && isAuthenticated) {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await register(username, email, password)
      navigate('/')
    } catch (err) {
      if (err instanceof ApiError && err.data) {
        const data = err.data as Record<string, string[] | string>
        const parts = Object.entries(data).map(([k, v]) =>
          Array.isArray(v) ? `${k}: ${v.join(', ')}` : `${k}: ${v}`,
        )
        setError(parts.join(' · ') || err.message)
      } else {
        setError('Błąd rejestracji')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0f1115] px-4">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800/80 bg-[#13161c] p-8 shadow-xl shadow-black/20">
        <h1 className="text-2xl font-semibold text-white">Rejestracja</h1>
        <p className="mt-2 text-sm text-zinc-500">Utwórz konto (hasło min. 8 znaków)</p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-500">
              Nazwa użytkownika
            </label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-zinc-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-500">
              E-mail
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-zinc-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-500">
              Hasło
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-zinc-700/80 bg-zinc-900/50 px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-zinc-500"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-400">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-zinc-100 py-2.5 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:opacity-50"
          >
            {submitting ? 'Tworzenie konta…' : 'Zarejestruj'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-zinc-500">
          Masz konto?{' '}
          <Link to="/login" className="text-zinc-300 hover:text-white">
            Zaloguj się
          </Link>
        </p>
      </div>
    </div>
  )
}
