import { randomUUID } from "node:crypto";

import { JOB_NAMES, QUEUE_NAMES } from "../queues/constants.js";
import { createReminderQueue, type ReminderQueueJob } from "../queues/factory.js";
import { getQueueJobOptions } from "../queues/options.js";
import type { QueuePublisherClient } from "../queues/publishers/invoiceQueuePublisher.js";
import type { InvoiceReminderSendJob } from "../types/jobs.js";

const DEFAULT_SMOKE_DELAY_MS = 30_000;

export type ReminderSmokeResult = {
  status: "queued" | "already_exists" | "failed";
  job_id: string;
  scheduled_for: string;
  delay_ms: number;
  error?: string;
};

export async function enqueueDelayedReminderSmokeJob(params: {
  delayMs?: number;
  now?: Date;
  correlationId?: string;
  queue?: QueuePublisherClient<ReminderQueueJob>;
} = {}): Promise<ReminderSmokeResult> {
  const delayMs = params.delayMs ?? DEFAULT_SMOKE_DELAY_MS;
  if (!Number.isInteger(delayMs) || delayMs <= 0) {
    throw new Error("delayMs must be a positive integer.");
  }

  const now = params.now ?? new Date();
  const correlationId = params.correlationId ?? randomUUID();
  const scheduledFor = new Date(now.getTime() + delayMs).toISOString();
  const jobId = `smoke:reminder:${correlationId}`;
  const queue = params.queue ?? createReminderQueue();
  const closeQueue = params.queue === undefined;

  try {
    const existingJob = await queue.getJob(jobId);
    if (existingJob) {
      return smokeResult("already_exists", jobId, scheduledFor, delayMs);
    }

    await queue.add(
      JOB_NAMES.INVOICE_REMINDER_SEND,
      smokePayload(correlationId, scheduledFor),
      getQueueJobOptions(QUEUE_NAMES.REMINDER, { jobId, delay: delayMs }),
    );

    return smokeResult("queued", jobId, scheduledFor, delayMs);
  } catch (error) {
    return {
      ...smokeResult("failed", jobId, scheduledFor, delayMs),
      error: error instanceof Error ? error.message : "Failed to enqueue smoke reminder.",
    };
  } finally {
    if (closeQueue) {
      await queue.close();
    }
  }
}

function smokePayload(correlationId: string, scheduledFor: string): InvoiceReminderSendJob {
  return {
    schemaVersion: 1,
    invoiceId: `smoke_${correlationId}`,
    orgId: "smoke",
    reminderOffsetDays: 0,
    scheduledFor,
    sendEventId: `smoke:${correlationId}`,
  };
}

function smokeResult(
  status: ReminderSmokeResult["status"],
  jobId: string,
  scheduledFor: string,
  delayMs: number,
): ReminderSmokeResult {
  return {
    status,
    job_id: jobId,
    scheduled_for: scheduledFor,
    delay_ms: delayMs,
  };
}
