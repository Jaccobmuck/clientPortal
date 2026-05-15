import assert from "node:assert/strict";
import { test } from "node:test";

import { JOB_NAMES, QUEUE_NAMES } from "../queues/constants.js";
import { createSmokeJobIds } from "../queues/health.js";
import {
  invoiceInitialEmailJobId,
  invoicePdfJobId,
  invoiceReminderJobId,
  invoiceReminderScheduleJobId,
  stripeWebhookJobId,
} from "../queues/jobIds.js";
import { DEFAULT_JOB_OPTIONS, QUEUE_JOB_OPTIONS } from "../queues/options.js";
import {
  enqueueInvoicePdfJob,
  type QueuePublisherClient,
} from "../queues/publishers/invoiceQueuePublisher.js";
import { assertRedisConfigured, queueHealthCheck } from "../queues/redis.js";
import type { InvoicePdfJob } from "../types/jobs.js";

test("queue constants match locked names", () => {
  assert.deepEqual(QUEUE_NAMES, {
    PDF: "pdf-queue",
    EMAIL: "email-queue",
    REMINDER: "reminder-queue",
    STRIPE_WEBHOOK: "stripe-webhook-queue",
  });
});

test("default and queue-specific job options use exponential backoff", () => {
  assert.equal(DEFAULT_JOB_OPTIONS.attempts, 3);
  assert.deepEqual(DEFAULT_JOB_OPTIONS.backoff, {
    type: "exponential",
    delay: 10_000,
  });
  assert.equal(QUEUE_JOB_OPTIONS[QUEUE_NAMES.PDF].attempts, 3);
  assert.equal(QUEUE_JOB_OPTIONS[QUEUE_NAMES.EMAIL].attempts, 5);
  assert.equal(QUEUE_JOB_OPTIONS[QUEUE_NAMES.REMINDER].attempts, 3);
  assert.equal(QUEUE_JOB_OPTIONS[QUEUE_NAMES.STRIPE_WEBHOOK].attempts, 5);
  assert.ok(
    Number(QUEUE_JOB_OPTIONS[QUEUE_NAMES.EMAIL].attempts) >
      Number(QUEUE_JOB_OPTIONS[QUEUE_NAMES.PDF].attempts),
  );
  assert.deepEqual(QUEUE_JOB_OPTIONS[QUEUE_NAMES.REMINDER].backoff, {
    type: "exponential",
    delay: 60_000,
  });
});

test("deterministic job IDs match expected formats", () => {
  const invoiceId = "inv_123";

  assert.equal(invoicePdfJobId(invoiceId), "invoice:inv_123:pdf:v1");
  assert.equal(
    invoiceInitialEmailJobId(invoiceId),
    "invoice:inv_123:initial-email:v1",
  );
  assert.equal(
    invoiceReminderScheduleJobId(invoiceId),
    "invoice:inv_123:reminder-schedule:v1",
  );
  assert.equal(invoiceReminderJobId(invoiceId, 7), "invoice:inv_123:reminder:7:v1");
  assert.equal(stripeWebhookJobId("evt_123"), "stripe:event:evt_123:v1");
});

test("minimal payload types do not require invoice snapshots or sensitive fields", () => {
  const payload = {
    schemaVersion: 1,
    invoiceId: "inv_123",
    orgId: "org_123",
  } satisfies InvoicePdfJob;

  assert.equal(payload.invoiceId, "inv_123");
  assert.equal("pay_token" in payload, false);
  assert.equal("pay_url" in payload, false);
  assert.equal("invoice" in payload, false);
  assert.equal("client" in payload, false);
  assert.equal("org" in payload, false);
  assert.equal("pdfBytes" in payload, false);
  assert.equal("renderedHtml" in payload, false);
});

test("queue publisher uses deterministic IDs", async () => {
  const fakeQueue = new FakeQueue<InvoicePdfJob>();
  const result = await enqueueInvoicePdfJob(
    {
      schemaVersion: 1,
      invoiceId: "inv_123",
      orgId: "org_123",
    },
    fakeQueue,
  );

  assert.equal(result.status, "queued");
  assert.equal(result.jobId, "invoice:inv_123:pdf:v1");
  assert.equal(fakeQueue.addCalls[0]?.name, JOB_NAMES.INVOICE_PDF);
  assert.equal(fakeQueue.addCalls[0]?.options.jobId, "invoice:inv_123:pdf:v1");
});

test("queue publisher treats existing job as idempotent success", async () => {
  const fakeQueue = new FakeQueue<InvoicePdfJob>(["invoice:inv_123:pdf:v1"]);
  const result = await enqueueInvoicePdfJob(
    {
      schemaVersion: 1,
      invoiceId: "inv_123",
      orgId: "org_123",
    },
    fakeQueue,
  );

  assert.equal(result.status, "already_exists");
  assert.equal(fakeQueue.addCalls.length, 0);
});

test("smoke queue helper creates smoke job IDs", () => {
  assert.deepEqual(createSmokeJobIds("run_123"), {
    pdf: "smoke:pdf:run_123",
    email: "smoke:email:run_123",
    reminder: "smoke:reminder:run_123",
  });
});

test("missing REDIS_URL fails clearly", async () => {
  assert.throws(() => assertRedisConfigured({}), /REDIS_URL is required/);

  const result = await queueHealthCheck({});
  assert.deepEqual(result, {
    status: "config_error",
    error: "REDIS_URL is required for BullMQ workers.",
  });
});

class FakeQueue<T> implements QueuePublisherClient<T> {
  readonly addCalls: Array<{
    name: string;
    data: T;
    options: { jobId?: string | number };
  }> = [];

  private readonly existingJobIds: Set<string>;

  constructor(existingJobIds: string[] = []) {
    this.existingJobIds = new Set(existingJobIds);
  }

  async getJob(jobId: string): Promise<unknown> {
    return this.existingJobIds.has(jobId) ? { id: jobId } : undefined;
  }

  async add(name: string, data: T, options: { jobId?: string | number }): Promise<unknown> {
    this.addCalls.push({ name, data, options });
    if (options.jobId) {
      this.existingJobIds.add(String(options.jobId));
    }

    return { id: options.jobId };
  }

  async close(): Promise<void> {
    return undefined;
  }
}
