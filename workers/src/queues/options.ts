import type { JobsOptions } from "bullmq";

import { QUEUE_NAMES, type QueueName } from "./constants.js";

export const DEFAULT_JOB_OPTIONS = {
  attempts: 3,
  backoff: {
    type: "exponential",
    delay: 10_000,
  },
  removeOnComplete: {
    age: 60 * 60 * 24 * 7,
    count: 1000,
  },
  removeOnFail: {
    age: 60 * 60 * 24 * 30,
    count: 5000,
  },
} satisfies JobsOptions;

export const QUEUE_JOB_OPTIONS = {
  [QUEUE_NAMES.PDF]: {
    ...DEFAULT_JOB_OPTIONS,
    attempts: 3,
    backoff: {
      type: "exponential",
      delay: 10_000,
    },
  },
  [QUEUE_NAMES.EMAIL]: {
    ...DEFAULT_JOB_OPTIONS,
    attempts: 5,
    backoff: {
      type: "exponential",
      delay: 30_000,
    },
  },
  [QUEUE_NAMES.REMINDER]: {
    ...DEFAULT_JOB_OPTIONS,
    attempts: 3,
    backoff: {
      type: "exponential",
      delay: 60_000,
    },
  },
  [QUEUE_NAMES.STRIPE_WEBHOOK]: {
    ...DEFAULT_JOB_OPTIONS,
    attempts: 5,
    backoff: {
      type: "exponential",
      delay: 30_000,
    },
  },
} satisfies Record<QueueName, JobsOptions>;

export const SMOKE_JOB_OPTIONS = {
  attempts: 1,
  removeOnComplete: {
    age: 60 * 60,
    count: 100,
  },
  removeOnFail: {
    age: 60 * 60,
    count: 100,
  },
} satisfies JobsOptions;

export function getQueueJobOptions(
  queueName: QueueName,
  overrides: JobsOptions = {},
): JobsOptions {
  const queueDefaults = QUEUE_JOB_OPTIONS[queueName];

  return {
    ...queueDefaults,
    ...overrides,
    backoff: overrides.backoff ?? queueDefaults.backoff,
    removeOnComplete: overrides.removeOnComplete ?? queueDefaults.removeOnComplete,
    removeOnFail: overrides.removeOnFail ?? queueDefaults.removeOnFail,
  };
}
