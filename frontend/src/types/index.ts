export type EmailCategory =
  | 'comp.graphics'
  | 'comp.os.ms-windows.misc'
  | 'comp.sys.ibm.pc.hardware'
  | 'comp.sys.mac.hardware'
  | 'comp.windows.x'
  | 'sci.electronics'
  | ''

export interface User {
  id: number
  username: string
  email: string
}

export interface Mailbox {
  id: number
  user: number
  name: string
  username: string
  imap_host: string
  imap_port: number
  smtp_host: string
  smtp_port: number
}

export interface CreateMailboxPayload {
  name: string
  username: string
  password: string
  imap_host: string
  imap_port: number
  smtp_host: string
  smtp_port: number
}

export interface EmailMessage {
  id: number
  mailbox: number
  subject: string
  sender: string
  body_text: string
  received_at: string
  processed: boolean
  category: EmailCategory
  priority_score: number | null
  ai_summary: string
  ai_draft_reply: string
  thread_summary: string
}

export interface TokenPair {
  access: string
  refresh: string
}

export interface FetchEmailsResponse {
  status: string
  total_new_emails: number
  details: Record<string, number>
}
