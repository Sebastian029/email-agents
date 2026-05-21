import { apiRequest } from './client'
import type {
  CreateMailboxPayload,
  EmailCategory,
  EmailMessage,
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
}) {
  const search = new URLSearchParams()
  if (params?.category) search.set('category', params.category)
  if (params?.processed !== undefined) {
    search.set('processed', String(params.processed))
  }

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
}) {
  return apiRequest<{ status: string; to: string }>('/emails/send/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchThreadSummary(emailId: number) {
  return apiRequest<{
    email_id: number
    subject: string
    thread_summary: string
  }>(`/emails/thread-summary/${emailId}/`)
}
