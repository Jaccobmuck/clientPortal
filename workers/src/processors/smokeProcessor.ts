import { Worker, type Job, type Processor } from "bullmq";

import {
  INVOICE_QUEUE_NAMES,
  JOB_NAMES,
  type InvoiceQueueName,
} from "../queues/constants.js";
import { getSharedRedisConnection } from "../queues/redis.js";
import type { SmokeQueueJob } from "../types/jobs.js";

export function createSmokeProcessor(queueName: InvoiceQueueName): Processor<SmokeQueueJob> {
  return async (job: Job<SmokeQueueJob>) => {
    if (job.name !== JOB_NAMES.SMOKE_NOOP || !isSmokeQueueJob(job.data, queueName)) {
      throw new Error(
        `[${queueName}] business processor is not implemented; only smoke jobs are supported.`,
      );
    }

    console.log(`[${queueName}] smoke job completed`, {
      jobId: job.id,
      correlationId: job.data.correlationId,
    });
  };
}

export function createSmokeWorkers(): Worker<SmokeQueueJob>[] {
  return createSmokeWorkersForQueues(INVOICE_QUEUE_NAMES);
}

export function createSmokeWorkersForQueues(
  queueNames: readonly InvoiceQueueName[],
): Worker<SmokeQueueJob>[] {
  return queueNames.map(
    (queueName) =>
      new Worker<SmokeQueueJob>(queueName, createSmokeProcessor(queueName), {
        connection: getSharedRedisConnection(),
      }),
  );
}

function isSmokeQueueJob(value: unknown, queueName: InvoiceQueueName): value is SmokeQueueJob {
  if (!value || typeof value !== "object") {
    return false;
  }

  const data = value as Partial<SmokeQueueJob>;
  return (
    data.schemaVersion === 1 &&
    data.smoke === true &&
    data.queueName === queueName &&
    typeof data.correlationId === "string" &&
    typeof data.requestedAt === "string"
  );
}
