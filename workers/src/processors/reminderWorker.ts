import { Worker, type Job, type Processor } from "bullmq";

import { JOB_NAMES, QUEUE_NAMES } from "../queues/constants.js";
import { getSharedRedisConnection } from "../queues/redis.js";
import type { InvoiceReminderScheduleJob, InvoiceReminderSendJob } from "../types/jobs.js";
import {
  createReminderScheduleProcessor,
  type ReminderScheduleProcessorDeps,
} from "./reminderScheduleProcessor.js";
import {
  createReminderSendProcessor,
  type ReminderSendProcessorDeps,
} from "./reminderSendProcessor.js";

export type ReminderWorkerDeps = {
  schedule?: Partial<ReminderScheduleProcessorDeps>;
  send?: Partial<ReminderSendProcessorDeps>;
};

export function createReminderProcessor(deps: ReminderWorkerDeps = {}): Processor {
  const scheduleProcessor = createReminderScheduleProcessor(deps.schedule);
  const sendProcessor = createReminderSendProcessor(deps.send);

  return async (job: Job) => {
    if (job.name === JOB_NAMES.INVOICE_REMINDER_SCHEDULE) {
      return scheduleProcessor(job as Job<InvoiceReminderScheduleJob>);
    }

    if (job.name === JOB_NAMES.INVOICE_REMINDER_SEND) {
      return sendProcessor(job as Job<InvoiceReminderSendJob>);
    }

    throw new Error(`[${QUEUE_NAMES.REMINDER}] unsupported reminder job.`);
  };
}

export function createReminderWorker(deps: ReminderWorkerDeps = {}): Worker {
  return new Worker(QUEUE_NAMES.REMINDER, createReminderProcessor(deps), {
    connection: getSharedRedisConnection(),
  });
}

export function createReminderWorkers(deps: ReminderWorkerDeps = {}): Worker[] {
  return [createReminderWorker(deps)];
}
