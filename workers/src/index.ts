import { createEmailWorker } from "./processors/emailWorker.js";
import { createSmokeWorkers, createSmokeWorkersForQueues } from "./processors/smokeProcessor.js";
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

  const emailWorkerEnabled = process.env.ENABLE_EMAIL_WORKER === "true";

  if (emailWorkerEnabled) {
    createEmailWorker();
    console.log("Email worker started", { queue: QUEUE_NAMES.EMAIL });
  }

  if (process.env.ENABLE_SMOKE_TESTS === "true") {
    if (emailWorkerEnabled) {
      createSmokeWorkersForQueues([QUEUE_NAMES.PDF, QUEUE_NAMES.REMINDER]);
      console.log("Smoke workers started", {
        queues: [QUEUE_NAMES.PDF, QUEUE_NAMES.REMINDER],
        note: "email queue handled by email worker",
      });
    } else {
      createSmokeWorkers();
      console.log("Smoke workers started", {
        queues: [QUEUE_NAMES.PDF, QUEUE_NAMES.EMAIL, QUEUE_NAMES.REMINDER],
      });
    }
  }

  if (!emailWorkerEnabled && process.env.ENABLE_SMOKE_TESTS !== "true") {
    console.log("Worker queue foundation loaded; business processors are not registered yet.");
  }
}
