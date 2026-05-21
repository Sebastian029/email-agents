import type { EmailCategory } from '../types'

export const CATEGORIES: {
  id: EmailCategory
  label: string
  color: string
}[] = [
  { id: 'complaint', label: 'Skargi', color: 'bg-rose-500/20 text-rose-300' },
  { id: 'refund', label: 'Zwroty', color: 'bg-amber-500/20 text-amber-300' },
  {
    id: 'technical_issue',
    label: 'Techniczne',
    color: 'bg-sky-500/20 text-sky-300',
  },
  {
    id: 'account_issue',
    label: 'Konto',
    color: 'bg-violet-500/20 text-violet-300',
  },
  {
    id: 'order_status',
    label: 'Zamówienia',
    color: 'bg-emerald-500/20 text-emerald-300',
  },
  { id: 'spam', label: 'Spam', color: 'bg-zinc-500/20 text-zinc-400' },
  { id: 'other', label: 'Inne', color: 'bg-zinc-600/20 text-zinc-300' },
]

export function categoryLabel(cat: EmailCategory): string {
  if (!cat) return 'Bez kategorii'
  return CATEGORIES.find((c) => c.id === cat)?.label ?? cat
}

export function categoryColor(cat: EmailCategory): string {
  if (!cat) return 'bg-zinc-700/40 text-zinc-400'
  return CATEGORIES.find((c) => c.id === cat)?.color ?? 'bg-zinc-700/40 text-zinc-400'
}
