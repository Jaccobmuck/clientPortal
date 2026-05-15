import { createSmokeWorkers } from "./processors/smokeProcessor.js";
import { QUEUE_NAMES } from "./queues/constants.js";
import { assertRedisConfigured } from "./queues/redis.js";

export { QUEUE_NAMES } from "./queues/constants.js";
export { createQueue } from "./queues/factory.js";
export { enqueueSmokeQueueJobs, queueHealthCheck } from "./queues/health.js";
export {
  enqueueInvoiceInitialEmailJob,
  enqueueInvoicePdfJob,
  enqueueInvoiceReminderScheduleJob,
  ensureInvoiceSendJobs,
} from "./queues/publishers/invoiceQueuePublisher.js";

if (process.env.NODE_ENV !== "test") {
  assertRedisConfigured();

  if (process.env.ENABLE_SMOKE_TESTS === "true") {
    createSmokeWorkers();
    console.log("Smoke workers started", {
      queues: [QUEUE_NAMES.PDF, QUEUE_NAMES.EMAIL, QUEUE_NAMES.REMINDER],
    });
  } else {
    console.log("Worker queue foundation loaded; business processors are not registered yet.");
  }
}
