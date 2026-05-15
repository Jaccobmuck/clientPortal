import type { JobsOptions } from "bullmq";

import { JOB_NAMES, QUEUE_NAMES, type QueueName } from "../constants.js";
import {
  createEmailQueue,
  createPdfQueue,
  createReminderQueue,
  type EmailQueueJob,
  type PdfQueueJob,
  type ReminderQueueJob,
} from "../factory.js";
import {
  invoiceInitialEmailJobId,
  invoicePdfJobId,
  invoiceReminderScheduleJobId,
} from "../jobIds.js";
import { getQueueJobOptions } from "../options.js";
import type {
  InvoiceEmailJob,
  InvoicePdfJob,
  InvoiceReminderScheduleJob,
} from "../../types/jobs.js";

export type QueuePublishStatus = "queued" | "already_exists" | "failed";

export type QueuePublishResult = {
  queueName: QueueName;
  jobId: string;
  status: QueuePublishStatus;
  error?: string;
};

export type InvoiceSendJobsResult = {
  pdf: QueuePublishResult;
  email: QueuePublishResult;
  reminders: QueuePublishResult;
};

export type QueuePublisherClient<T> = {
  add(name: string, data: T, options: JobsOptions): Promise<unknown>;
  getJob(jobId: string): Promise<unknown>;
  close(): Promise<void>;
};

export async function enqueueInvoicePdfJob(
  payload: InvoicePdfJob,
  queue?: QueuePublisherClient<PdfQueueJob>,
): Promise<QueuePublishResult> {
  const queueClient = queue ?? createPdfQueue();

  return enqueueIdempotentJob({
    queue: queueClient,
    queueName: QUEUE_NAMES.PDF,
    jobName: JOB_NAMES.INVOICE_PDF,
    payload,
    jobId: invoicePdfJobId(payload.invoiceId),
    closeQueue: queue === undefined,
  });
}

export async function enqueueInvoiceInitialEmailJob(
  payload: InvoiceEmailJob,
  queue?: QueuePublisherClient<EmailQueueJob>,
): Promise<QueuePublishResult> {
  const queueClient = queue ?? createEmailQueue();

  return enqueueIdempotentJob({
    queue: queueClient,
    queueName: QUEUE_NAMES.EMAIL,
    jobName: JOB_NAMES.INVOICE_INITIAL_EMAIL,
    payload,
    jobId: invoiceInitialEmailJobId(payload.invoiceId),
    closeQueue: queue === undefined,
  });
}

export async function enqueueInvoiceReminderScheduleJob(
  payload: InvoiceReminderScheduleJob,
  queue?: QueuePublisherClient<ReminderQueueJob>,
): Promise<QueuePublishResult> {
  const queueClient = queue ?? createReminderQueue();

  return enqueueIdempotentJob({
    queue: queueClient,
    queueName: QUEUE_NAMES.REMINDER,
    jobName: JOB_NAMES.INVOICE_REMINDER_SCHEDULE,
    payload,
    jobId: invoiceReminderScheduleJobId(payload.invoiceId),
    closeQueue: queue === undefined,
  });
}

export async function ensureInvoiceSendJobs(payload: {
  invoiceId: string;
  orgId: string;
  requestedByUserId?: string;
  sendEventId?: string;
}): Promise<InvoiceSendJobsResult> {
  const commonPayload = {
    schemaVersion: 1,
    invoiceId: payload.invoiceId,
    orgId: payload.orgId,
    requestedByUserId: payload.requestedByUserId,
    sendEventId: payload.sendEventId,
  } satisfies InvoicePdfJob | InvoiceReminderScheduleJob;

  const [pdf, email, reminders] = await Promise.all([
    enqueueInvoicePdfJob(commonPayload),
    enqueueInvoiceInitialEmailJob({
      ...commonPayload,
      emailType: "invoice_sent",
    }),
    enqueueInvoiceReminderScheduleJob(commonPayload),
  ]);

  return { pdf, email, reminders };
}

async function enqueueIdempotentJob<T>(params: {
  queue: QueuePublisherClient<T>;
  queueName: QueueName;
  jobName: string;
  payload: T;
  jobId: string;
  options?: JobsOptions;
  closeQueue: boolean;
}): Promise<QueuePublishResult> {
  const { queue, queueName, jobName, payload, jobId, options, closeQueue } = params;

  try {
    const existingJob = await queue.getJob(jobId);
    if (existingJob) {
      return { queueName, jobId, status: "already_exists" };
    }

    await queue.add(jobName, payload, getQueueJobOptions(queueName, { ...options, jobId }));
    return { queueName, jobId, status: "queued" };
  } catch (error) {
    const existingJob = await safelyGetExistingJob(queue, jobId);
    if (existingJob) {
      return { queueName, jobId, status: "already_exists" };
    }

    const safeMessage = safeQueueErrorMessage(error);
    console.error(`[${queueName}] failed to enqueue job`, {
      jobId,
      error: safeMessage,
    });

    return {
      queueName,
      jobId,
      status: "failed",
      error: safeMessage,
    };
  } finally {
    if (closeQueue) {
      await safelyCloseQueue(queue);
    }
  }
}

async function safelyGetExistingJob<T>(
  queue: QueuePublisherClient<T>,
  jobId: string,
): Promise<unknown> {
  try {
    return await queue.getJob(jobId);
  } catch {
    return undefined;
  }
}

async function safelyCloseQueue<T>(queue: QueuePublisherClient<T>): Promise<void> {
  try {
    await queue.close();
  } catch {
    return undefined;
  }
}

function safeQueueErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message.replace(/rediss?:\/\/[^\s]+/gi, "redis://***");
  }

  return "Failed to enqueue BullMQ job.";
}
