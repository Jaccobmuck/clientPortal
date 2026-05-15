export const QUEUE_NAMES = {
  PDF: "pdf-queue",
  EMAIL: "email-queue",
  REMINDER: "reminder-queue",
  STRIPE_WEBHOOK: "stripe-webhook-queue",
} as const;

export type QueueName = (typeof QUEUE_NAMES)[keyof typeof QUEUE_NAMES];

export const INVOICE_QUEUE_NAMES = [
  QUEUE_NAMES.PDF,
  QUEUE_NAMES.EMAIL,
  QUEUE_NAMES.REMINDER,
] as const;

export type InvoiceQueueName = (typeof INVOICE_QUEUE_NAMES)[number];

export const JOB_NAMES = {
  INVOICE_PDF: "invoice.pdf",
  INVOICE_INITIAL_EMAIL: "invoice.email.initial",
  INVOICE_REMINDER_SCHEDULE: "invoice.reminder.schedule",
  INVOICE_REMINDER_SEND: "invoice.reminder.send",
  STRIPE_WEBHOOK: "stripe.webhook",
  SMOKE_NOOP: "smoke.noop",
} as const;

export type JobName = (typeof JOB_NAMES)[keyof typeof JOB_NAMES];
