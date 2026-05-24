import type { EmailCategory } from '../types'

export const CATEGORIES: {
  id: EmailCategory
  label: string
  color: string
}[] = [
  {
    id: 'comp.graphics',
    label: 'Grafika',
    color: 'bg-rose-500/20 text-rose-300',
  },
  {
    id: 'comp.os.ms-windows.misc',
    label: 'Windows',
    color: 'bg-amber-500/20 text-amber-300',
  },
  {
    id: 'comp.sys.ibm.pc.hardware',
    label: 'PC hardware',
    color: 'bg-sky-500/20 text-sky-300',
  },
  {
    id: 'comp.sys.mac.hardware',
    label: 'Mac hardware',
    color: 'bg-violet-500/20 text-violet-300',
  },
  {
    id: 'comp.windows.x',
    label: 'X Window',
    color: 'bg-emerald-500/20 text-emerald-300',
  },
  {
    id: 'sci.electronics',
    label: 'Elektronika',
    color: 'bg-orange-500/20 text-orange-300',
  },
]

export function categoryLabel(cat: EmailCategory): string {
  if (!cat) return 'Bez kategorii'
  return CATEGORIES.find((c) => c.id === cat)?.label ?? cat
}

export function categoryColor(cat: EmailCategory): string {
  if (!cat) return 'bg-zinc-700/40 text-zinc-400'
  return CATEGORIES.find((c) => c.id === cat)?.color ?? 'bg-zinc-700/40 text-zinc-400'
}
