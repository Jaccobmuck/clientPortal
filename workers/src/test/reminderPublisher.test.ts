import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { JOB_NAMES, QUEUE_NAMES } from "../queues/constants.js";
import type { QueuePublisherClient } from "../queues/publishers/invoiceQueuePublisher.js";
import {
  enqueueDelayedReminderJob,
  enqueueOverdueReminderEmailJob,
  overdueReminderEmailJobId,
} from "../reminders/publisher.js";
import type { InvoiceEmailJob, InvoiceReminderSendJob } from "../types/jobs.js";

const SEND_PAYLOAD = {
  schemaVersion: 1,
  invoiceId: "inv_123",
  orgId: "org_123",
  reminderOffsetDays: 3,
  scheduledFor: "2026-05-13T09:00:00.000Z",
  sendEventId: "send_123",
} satisfies InvoiceReminderSendJob;

describe("reminder publisher helpers", () => {
  test("enqueues delayed reminder jobs with deterministic IDs and millisecond delay", async () => {
    const queue = new FakeQueue<InvoiceReminderSendJob>();
    const result = await enqueueDelayedReminderJob(SEND_PAYLOAD, 30_000, queue);

    assert.equal(result.status, "queued");
    assert.equal(result.queueName, QUEUE_NAMES.REMINDER);
    assert.equal(result.jobId, "invoice:inv_123:reminder:3:v1");
    assert.equal(queue.addCalls[0]?.name, JOB_NAMES.INVOICE_REMINDER_SEND);
    assert.equal(queue.addCalls[0]?.options.delay, 30_000);
    assert.equal(queue.addCalls[0]?.options.jobId, "invoice:inv_123:reminder:3:v1");
  });

  test("treats an existing delayed reminder job as idempotent success", async () => {
    const queue = new FakeQueue<InvoiceReminderSendJob>(["invoice:inv_123:reminder:3:v1"]);
    const result = await enqueueDelayedReminderJob(SEND_PAYLOAD, 30_000, queue);

    assert.equal(result.status, "already_exists");
    assert.equal(queue.addCalls.length, 0);
  });

  test("enqueues overdue reminder email payloads without templates or provider calls", async () => {
    const queue = new FakeQueue<InvoiceEmailJob>();
    const result = await enqueueOverdueReminderEmailJob(SEND_PAYLOAD, queue);

    assert.equal(result.status, "queued");
    assert.equal(result.queueName, QUEUE_NAMES.EMAIL);
    assert.equal(result.jobId, "invoice:inv_123:overdue-reminder:3:v1");
    assert.equal(queue.addCalls[0]?.name, JOB_NAMES.INVOICE_REMINDER_EMAIL);
    assert.deepEqual(queue.addCalls[0]?.data, {
      schemaVersion: 1,
      invoiceId: "inv_123",
      orgId: "org_123",
      emailType: "overdue_reminder",
      sendEventId: "send_123",
      reminderOffsetDays: 3,
    });
  });

  test("uses deterministic overdue reminder email job IDs", () => {
    assert.equal(
      overdueReminderEmailJobId("inv_123", -3),
      "invoice:inv_123:overdue-reminder:-3:v1",
    );
  });
});

class FakeQueue<T> implements QueuePublisherClient<T> {
  readonly addCalls: Array<{
    name: string;
    data: T;
    options: { jobId?: string | number; delay?: number };
  }> = [];

  private readonly existingJobIds: Set<string>;

  constructor(existingJobIds: string[] = []) {
    this.existingJobIds = new Set(existingJobIds);
  }

  async getJob(jobId: string): Promise<unknown> {
    return this.existingJobIds.has(jobId) ? { id: jobId } : undefined;
  }

  async add(
    name: string,
    data: T,
    options: { jobId?: string | number; delay?: number },
  ): Promise<unknown> {
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
