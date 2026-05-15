import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { JOB_NAMES } from "../queues/constants.js";
import type { QueuePublisherClient } from "../queues/publishers/invoiceQueuePublisher.js";
import { enqueueDelayedReminderSmokeJob } from "../reminders/smoke.js";
import type { InvoiceReminderSendJob } from "../types/jobs.js";

describe("reminder smoke helper", () => {
  test("schedules a 30 second delayed reminder smoke job", async () => {
    const queue = new FakeQueue<InvoiceReminderSendJob>();
    const result = await enqueueDelayedReminderSmokeJob({
      queue,
      correlationId: "run_123",
      now: new Date("2026-05-10T09:00:00.000Z"),
    });

    assert.deepEqual(result, {
      status: "queued",
      job_id: "smoke:reminder:run_123",
      scheduled_for: "2026-05-10T09:00:30.000Z",
      delay_ms: 30_000,
    });
    assert.equal(queue.addCalls[0]?.name, JOB_NAMES.INVOICE_REMINDER_SEND);
    assert.equal(queue.addCalls[0]?.options.delay, 30_000);
    assert.equal(queue.addCalls[0]?.options.jobId, "smoke:reminder:run_123");
    assert.equal(queue.addCalls[0]?.data.invoiceId, "smoke_run_123");
  });

  test("allows a custom delay for fast local checks", async () => {
    const queue = new FakeQueue<InvoiceReminderSendJob>();
    const result = await enqueueDelayedReminderSmokeJob({
      queue,
      delayMs: 1_000,
      correlationId: "run_123",
      now: new Date("2026-05-10T09:00:00.000Z"),
    });

    assert.equal(result.delay_ms, 1_000);
    assert.equal(result.scheduled_for, "2026-05-10T09:00:01.000Z");
  });
});

class FakeQueue<T> implements QueuePublisherClient<T> {
  readonly addCalls: Array<{
    name: string;
    data: T;
    options: { jobId?: string | number; delay?: number };
  }> = [];

  async getJob(): Promise<unknown> {
    return undefined;
  }

  async add(
    name: string,
    data: T,
    options: { jobId?: string | number; delay?: number },
  ): Promise<unknown> {
    this.addCalls.push({ name, data, options });
    return { id: options.jobId };
  }

  async close(): Promise<void> {
    return undefined;
  }
}
