import type { InvoiceQueueName } from "../queues/constants.js";

export type InvoicePdfJob = {
  schemaVersion: 1;
  invoiceId: string;
  orgId: string;
  requestedByUserId?: string;
  sendEventId?: string;
};

export type InvoiceEmailJob = {
  schemaVersion: 1;
  invoiceId: string;
  orgId: string;
  emailType:
    | "invoice_sent"
    | "payment_received"
    | "payment_confirmed"
    | "overdue_reminder";
  requestedByUserId?: string;
  sendEventId?: string;
  reminderOffsetDays?: number;
};

export type InvoiceReminderScheduleJob = {
  schemaVersion: 1;
  invoiceId: string;
  orgId: string;
  requestedByUserId?: string;
  sendEventId?: string;
};

export type InvoiceReminderSendJob = {
  schemaVersion: 1;
  invoiceId: string;
  orgId: string;
  reminderOffsetDays: number;
  scheduledFor: string;
  sendEventId?: string;
};

export type StripeWebhookJob = {
  schemaVersion: 1;
  eventId: string;
  eventType: string;
  receivedAt: string;
};

export type SmokeQueueJob = {
  schemaVersion: 1;
  smoke: true;
  queueName: InvoiceQueueName;
  correlationId: string;
  requestedAt: string;
};
