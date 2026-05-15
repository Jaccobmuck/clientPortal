import { createPdfWorker } from "./processors/pdfWorker.js";
import { createSmokeWorkers } from "./processors/smokeProcessor.js";
import { QUEUE_NAMES } from "./queues/constants.js";
import { assertRedisConfigured } from "./queues/redis.js";

export type WorkerStartupStatus = "idle" | "smoke_workers_started" | "workers_started";

export function startWorkerProcess(env: NodeJS.ProcessEnv = process.env): WorkerStartupStatus {
  if (env.ENABLE_SMOKE_TESTS === "true") {
    assertRedisConfigured(env);
    createSmokeWorkers();
    console.log("Smoke workers started", {
      queues: [QUEUE_NAMES.PDF, QUEUE_NAMES.EMAIL, QUEUE_NAMES.REMINDER],
    });
    return "smoke_workers_started";
  }

  if (env.REDIS_URL?.trim()) {
    assertRedisConfigured(env);
    createPdfWorker();
    console.log("PDF worker started", { queue: QUEUE_NAMES.PDF });
    return "workers_started";
  }

  console.warn(
    "Worker queue foundation loaded without REDIS_URL; no processors are registered yet.",
  );

  return "idle";
}
