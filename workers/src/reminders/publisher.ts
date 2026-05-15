import type { JobsOptions } from "bullmq";

import { JOB_NAMES, QUEUE_NAMES, type QueueName } from "../queues/constants.js";
import {
  createEmailQueue,
  createReminderQueue,
  type EmailQueueJob,
  type ReminderQueueJob,
} from "../queues/factory.js";
import { invoiceReminderJobId } from "../queues/jobIds.js";
import { getQueueJobOptions } from "../queues/options.js";
import type {
  QueuePublishResult,
  QueuePublisherClient,
} from "../queues/publishers/invoiceQueuePublisher.js";
import type { InvoiceEmailJob, InvoiceReminderSendJob } from "../types/jobs.js";

const SCHEMA_VERSION = 1;

export async function enqueueDelayedReminderJob(
  payload: InvoiceReminderSendJob,
  delayMs: number,
  queue?: QueuePublisherClient<ReminderQueueJob>,
): Promise<QueuePublishResult> {
  if (!Number.isInteger(delayMs) || delayMs < 0) {
    throw new Error("delayMs must be a non-negative integer.");
  }

  const queueClient = queue ?? createReminderQueue();

  return enqueueIdempotentJob({
    queue: queueClient,
    queueName: QUEUE_NAMES.REMINDER,
    jobName: JOB_NAMES.INVOICE_REMINDER_SEND,
    payload,
    jobId: invoiceReminderJobId(payload.invoiceId, payload.reminderOffsetDays),
    options: { delay: delayMs },
    closeQueue: queue === undefined,
  });
}

export async function enqueueOverdueReminderEmailJob(
  payload: InvoiceReminderSendJob,
  queue?: QueuePublisherClient<EmailQueueJob>,
): Promise<QueuePublishResult> {
  const queueClient = queue ?? createEmailQueue();
  const emailPayload: InvoiceEmailJob = {
    schemaVersion: 1,
    invoiceId: payload.invoiceId,
    orgId: payload.orgId,
    emailType: "overdue_reminder",
    sendEventId: payload.sendEventId,
    reminderOffsetDays: payload.reminderOffsetDays,
  };

  return enqueueIdempotentJob({
    queue: queueClient,
    queueName: QUEUE_NAMES.EMAIL,
    jobName: JOB_NAMES.INVOICE_REMINDER_EMAIL,
    payload: emailPayload,
    jobId: overdueReminderEmailJobId(payload.invoiceId, payload.reminderOffsetDays),
    closeQueue: queue === undefined,
  });
}

export function overdueReminderEmailJobId(invoiceId: string, offsetDays: number): string {
  if (!Number.isInteger(offsetDays)) {
    throw new Error("offsetDays must be an integer.");
  }

  return `invoice:${requiredId("invoiceId", invoiceId)}:overdue-reminder:${offsetDays}:v${SCHEMA_VERSION}`;
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
    console.error(`[${queueName}] failed to enqueue reminder job`, {
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

function requiredId(name: string, value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${name} is required.`);
  }

  return trimmed;
}
