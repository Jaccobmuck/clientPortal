import { Queue, type QueueOptions } from "bullmq";

import { QUEUE_NAMES, type QueueName } from "./constants.js";
import { getSharedRedisConnection } from "./redis.js";
import type {
  InvoiceEmailJob,
  InvoicePdfJob,
  InvoiceReminderScheduleJob,
  InvoiceReminderSendJob,
  SmokeQueueJob,
  StripeWebhookJob,
} from "../types/jobs.js";

export type PdfQueueJob = InvoicePdfJob | SmokeQueueJob;
export type EmailQueueJob = InvoiceEmailJob | SmokeQueueJob;
export type ReminderQueueJob =
  | InvoiceReminderScheduleJob
  | InvoiceReminderSendJob
  | SmokeQueueJob;

export function createQueue<T>(
  queueName: QueueName,
  options: Omit<QueueOptions, "connection"> = {},
): Queue<T> {
  return new Queue<T>(queueName, {
    ...options,
    connection: getSharedRedisConnection(),
  });
}

export function createPdfQueue(): Queue<PdfQueueJob> {
  return createQueue<PdfQueueJob>(QUEUE_NAMES.PDF);
}

export function createEmailQueue(): Queue<EmailQueueJob> {
  return createQueue<EmailQueueJob>(QUEUE_NAMES.EMAIL);
}

export function createReminderQueue(): Queue<ReminderQueueJob> {
  return createQueue<ReminderQueueJob>(QUEUE_NAMES.REMINDER);
}

export function createStripeWebhookQueue(): Queue<StripeWebhookJob> {
  return createQueue<StripeWebhookJob>(QUEUE_NAMES.STRIPE_WEBHOOK);
}
