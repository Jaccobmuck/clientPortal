import { startWorkerProcess } from "./runtime.js";

export { QUEUE_NAMES } from "./queues/constants.js";
export { createQueue } from "./queues/factory.js";
export { enqueueSmokeQueueJobs, queueHealthCheck } from "./queues/health.js";
export {
  enqueueInvoiceInitialEmailJob,
  enqueueInvoicePdfJob,
  enqueueInvoiceReminderScheduleJob,
  ensureInvoiceSendJobs,
} from "./queues/publishers/invoiceQueuePublisher.js";
export { createReminderWorker, createReminderWorkers } from "./processors/reminderWorker.js";
export { enqueueDelayedReminderSmokeJob } from "./reminders/smoke.js";
export { startWorkerProcess } from "./runtime.js";
export type { WorkerStartupStatus } from "./runtime.js";

if (process.env.NODE_ENV !== "test") {
  startWorkerProcess();
}
