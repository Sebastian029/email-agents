import { apiRequest } from './client'
import type {
  CreateMailboxPayload,
  EmailCategory,
  EmailMessage,
  EmailThreadResponse,
  FetchEmailsResponse,
  Mailbox,
} from '../types'

export function fetchMailboxes() {
  return apiRequest<Mailbox[]>('/emails/mailboxes/')
}

export function createMailbox(payload: CreateMailboxPayload) {
  return apiRequest<Mailbox>('/emails/mailboxes/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteMailbox(id: number) {
  return apiRequest<void>(`/emails/mailboxes/${id}/`, {
    method: 'DELETE',
  })
}

export function fetchEmailsFromServer() {
  return apiRequest<FetchEmailsResponse>('/emails/fetch/', {
    method: 'POST',
  })
}

export function listEmails(params?: {
  mailboxId?: number
  category?: EmailCategory
  processed?: boolean
  includeHidden?: boolean
}) {
  const search = new URLSearchParams()
  if (params?.category) search.set('category', params.category)
  if (params?.processed !== undefined) {
    search.set('processed', String(params.processed))
  }
  if (params?.includeHidden) search.set('include_hidden', 'true')

  const query = search.toString()
  const suffix = query ? `?${query}` : ''
  const base = params?.mailboxId
    ? `/emails/list/${params.mailboxId}/`
    : '/emails/list/'

  return apiRequest<EmailMessage[]>(`${base}${suffix}`)
}

export function sendEmail(payload: {
  mailbox: number
  to: string
  subject: string
  body: string
  reply_to_email_id?: number
}) {
  return apiRequest<{ status: string; to: string }>('/emails/send/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchEmailThread(emailId: number, includeHidden = false) {
  const q = includeHidden ? '?include_hidden=true' : ''
  return apiRequest<EmailThreadResponse>(`/emails/thread/${emailId}/${q}`)
}

export function hideEmail(emailId: number) {
  return apiRequest<{ status: string; email_id: number }>(
    `/emails/${emailId}/hide/`,
    { method: 'POST' },
  )
}

export function unhideEmail(emailId: number) {
  return apiRequest<{ status: string; email_id: number }>(
    `/emails/${emailId}/unhide/`,
    { method: 'POST' },
  )
}

export function deleteEmail(emailId: number) {
  return apiRequest<{ status: string; email_id: number }>(
    `/emails/${emailId}/delete/`,
    { method: 'DELETE' },
  )
}

export function hideThread(emailId: number) {
  return apiRequest<{ status: string; thread_id: string; updated_count: number }>(
    `/emails/thread/${emailId}/hide/`,
    { method: 'POST' },
  )
}

export function unhideThread(emailId: number) {
  return apiRequest<{ status: string; thread_id: string; updated_count: number }>(
    `/emails/thread/${emailId}/unhide/`,
    { method: 'POST' },
  )
}

export function deleteThread(emailId: number) {
  return apiRequest<{ status: string; thread_id: string; deleted_count: number }>(
    `/emails/thread/${emailId}/delete/`,
    { method: 'DELETE' },
  )
}

export function fetchThreadSummary(emailId: number) {
  return apiRequest<{
    email_id: number
    subject: string
    thread_summary: string
  }>(`/emails/thread-summary/${emailId}/`)
}
