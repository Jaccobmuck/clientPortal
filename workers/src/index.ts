/**
 * BullMQ worker entrypoint — P0 scaffold.
 * P7 will add actual processors (pdf, email, reminder).
 *
 * Queue names are the single source of truth — FastAPI enqueues to these
 * exact strings, workers consume from them.
 */

import { Worker, Queue } from "bullmq";
import { Redis } from "ioredis";

const REDIS_URL = process.env.REDIS_URL ?? "redis://localhost:6379";

export const connection = new Redis(REDIS_URL, {
  maxRetriesPerRequest: null, // required by BullMQ
});

// ── Queue name constants — import these in FastAPI enqueue helpers too ──
export const QUEUE_NAMES = {
  PDF: "pdf-queue",
  EMAIL: "email-queue",
  REMINDER: "reminder-queue",
} as const;

// ── Queue instances (used by producers) ───────────────────────────────────
export const queues = {
  pdf: new Queue(QUEUE_NAMES.PDF, { connection }),
  email: new Queue(QUEUE_NAMES.EMAIL, { connection }),
  reminder: new Queue(QUEUE_NAMES.REMINDER, { connection }),
};

// ── Worker stubs — processors added in P7 ────────────────────────────────
if (process.env.NODE_ENV !== "test") {
  new Worker(QUEUE_NAMES.PDF, async (job) => {
    console.log("[pdf-queue] job received:", job.id, "— processor TBD in P7");
  }, { connection });

  new Worker(QUEUE_NAMES.EMAIL, async (job) => {
    console.log("[email-queue] job received:", job.id, "— processor TBD in P7");
  }, { connection });

  new Worker(QUEUE_NAMES.REMINDER, async (job) => {
    console.log("[reminder-queue] job received:", job.id, "— processor TBD in P7");
  }, { connection });

  console.log("Workers started — listening on all queues");
}
