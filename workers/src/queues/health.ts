import { randomUUID } from "node:crypto";

import { JOB_NAMES, QUEUE_NAMES, type InvoiceQueueName } from "./constants.js";
import { createEmailQueue, createPdfQueue, createReminderQueue } from "./factory.js";
import { SMOKE_JOB_OPTIONS } from "./options.js";
import { queueHealthCheck } from "./redis.js";
import type { SmokeQueueJob } from "../types/jobs.js";

export { queueHealthCheck };

export type SmokeQueueStatus = "ok" | "failed";

export type SmokeQueueJobIds = {
  pdf: string;
  email: string;
  reminder: string;
};

export type SmokeQueueResult = {
  pdf_queue: SmokeQueueStatus;
  email_queue: SmokeQueueStatus;
  reminder_queue: SmokeQueueStatus;
  job_ids: SmokeQueueJobIds;
};

export function createSmokeJobIds(correlationId: string = randomUUID()): SmokeQueueJobIds {
  return {
    pdf: `smoke:pdf:${correlationId}`,
    email: `smoke:email:${correlationId}`,
    reminder: `smoke:reminder:${correlationId}`,
  };
}

export async function enqueueSmokeQueueJobs(
  correlationId = randomUUID(),
): Promise<SmokeQueueResult> {
  const jobIds = createSmokeJobIds(correlationId);
  const requestedAt = new Date().toISOString();

  const [pdfQueue, emailQueue, reminderQueue] = [
    createPdfQueue(),
    createEmailQueue(),
    createReminderQueue(),
  ];

  const [pdfResult, emailResult, reminderResult] = await Promise.allSettled([
    pdfQueue.add(
      JOB_NAMES.SMOKE_NOOP,
      smokePayload(QUEUE_NAMES.PDF, correlationId, requestedAt),
      { ...SMOKE_JOB_OPTIONS, jobId: jobIds.pdf },
    ),
    emailQueue.add(
      JOB_NAMES.SMOKE_NOOP,
      smokePayload(QUEUE_NAMES.EMAIL, correlationId, requestedAt),
      { ...SMOKE_JOB_OPTIONS, jobId: jobIds.email },
    ),
    reminderQueue.add(
      JOB_NAMES.SMOKE_NOOP,
      smokePayload(QUEUE_NAMES.REMINDER, correlationId, requestedAt),
      { ...SMOKE_JOB_OPTIONS, jobId: jobIds.reminder },
    ),
  ]);

  await Promise.allSettled([pdfQueue.close(), emailQueue.close(), reminderQueue.close()]);

  return {
    pdf_queue: settledStatus(pdfResult),
    email_queue: settledStatus(emailResult),
    reminder_queue: settledStatus(reminderResult),
    job_ids: jobIds,
  };
}

function smokePayload(
  queueName: InvoiceQueueName,
  correlationId: string,
  requestedAt: string,
): SmokeQueueJob {
  return {
    schemaVersion: 1,
    smoke: true,
    queueName,
    correlationId,
    requestedAt,
  };
}

function settledStatus(result: PromiseSettledResult<unknown>): SmokeQueueStatus {
  return result.status === "fulfilled" ? "ok" : "failed";
}
