import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-zinc-800 text-white'
      : 'text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200'
  }`

export function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="flex h-full min-h-screen bg-[#0f1115]">
      <aside className="flex w-56 shrink-0 flex-col border-r border-zinc-800/80 bg-[#13161c] px-4 py-6">
        <div className="mb-8 px-2">
          <h1 className="text-lg font-semibold tracking-tight text-white">
            Email Agents
          </h1>
          <p className="mt-1 text-xs text-zinc-500">AI inbox</p>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          <NavLink to="/" end className={navClass}>
            Skrzynka
          </NavLink>
          <NavLink to="/mailboxes" className={navClass}>
            Skrzynki pocztowe
          </NavLink>
        </nav>

        <div className="mt-auto border-t border-zinc-800/80 pt-4">
          <p className="truncate px-2 text-sm font-medium text-zinc-300">
            {user?.username}
          </p>
          <p className="truncate px-2 text-xs text-zinc-500">{user?.email}</p>
          <button
            type="button"
            onClick={logout}
            className="mt-3 w-full rounded-lg border border-zinc-700/80 px-3 py-2 text-sm text-zinc-400 transition hover:border-zinc-600 hover:bg-zinc-800/50 hover:text-zinc-200"
          >
            Wyloguj
          </button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
