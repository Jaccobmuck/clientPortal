import assert from "node:assert/strict";
import { describe, test } from "node:test";

import type { QueuePublishResult } from "../queues/publishers/invoiceQueuePublisher.js";
import {
  processReminderScheduleJob,
  type ReminderScheduleProcessorDeps,
} from "../processors/reminderScheduleProcessor.js";
import type { ReminderConfig, ReminderInvoice } from "../reminders/repository.js";
import type { InvoiceReminderSendJob } from "../types/jobs.js";

describe("reminder schedule processor", () => {
  test("loads invoice and org config before enqueuing delayed reminders", async () => {
    const deps = fakeDeps({
      invoice: {
        id: "inv_123",
        orgId: "org_123",
        status: "sent",
        dueDate: "2026-05-10",
      },
      config: {
        orgId: "org_123",
        timezone: "UTC",
        ruleSource: [{ offset_days: 0, enabled: true }],
      },
      now: new Date("2026-05-10T08:59:30.000Z"),
    });

    const result = await processReminderScheduleJob(
      {
        schemaVersion: 1,
        invoiceId: "inv_123",
        orgId: "org_123",
        sendEventId: "send_123",
      },
      deps,
    );

    assert.equal(result.status, "scheduled");
    assert.equal(result.scheduledCount, 1);
    assert.equal(deps.enqueued[0]?.delayMs, 30_000);
    assert.deepEqual(deps.enqueued[0]?.payload, {
      schemaVersion: 1,
      invoiceId: "inv_123",
      orgId: "org_123",
      reminderOffsetDays: 0,
      scheduledFor: "2026-05-10T09:00:00.000Z",
      sendEventId: "send_123",
    });
  });

  test("skips schedule creation for non-payable statuses", async () => {
    const deps = fakeDeps({
      invoice: { id: "inv_123", orgId: "org_123", status: "paid", dueDate: "2026-05-10" },
    });

    const result = await processReminderScheduleJob(
      { schemaVersion: 1, invoiceId: "inv_123", orgId: "org_123" },
      deps,
    );

    assert.equal(result.status, "skipped");
    assert.equal(result.reason, "status_noop");
    assert.equal(deps.enqueued.length, 0);
  });

  test("skips reminders whose scheduled time is already in the past", async () => {
    const deps = fakeDeps({
      invoice: {
        id: "inv_123",
        orgId: "org_123",
        status: "sent",
        dueDate: "2026-05-10",
      },
      config: {
        orgId: "org_123",
        ruleSource: [
          { offset_days: 0, enabled: true },
          { offset_days: 3, enabled: true },
        ],
      },
      now: new Date("2026-05-10T10:00:00.000Z"),
    });

    const result = await processReminderScheduleJob(
      { schemaVersion: 1, invoiceId: "inv_123", orgId: "org_123" },
      deps,
    );

    assert.equal(result.scheduledCount, 1);
    assert.equal(result.skippedPastCount, 1);
    assert.equal(deps.enqueued[0]?.payload.reminderOffsetDays, 3);
  });

  test("does not create delayed jobs when the invoice has no due date", async () => {
    const deps = fakeDeps({
      invoice: { id: "inv_123", orgId: "org_123", status: "sent", dueDate: null },
    });

    const result = await processReminderScheduleJob(
      { schemaVersion: 1, invoiceId: "inv_123", orgId: "org_123" },
      deps,
    );

    assert.equal(result.status, "skipped");
    assert.equal(result.reason, "missing_due_date");
  });
});

function fakeDeps(params: {
  invoice?: ReminderInvoice | null;
  config?: ReminderConfig | null;
  now?: Date;
}): ReminderScheduleProcessorDeps & {
  enqueued: Array<{ payload: InvoiceReminderSendJob; delayMs: number }>;
} {
  const enqueued: Array<{ payload: InvoiceReminderSendJob; delayMs: number }> = [];

  return {
    enqueued,
    now: () => params.now ?? new Date("2026-05-10T08:00:00.000Z"),
    dataSource: {
      async loadInvoice() {
        return params.invoice ?? null;
      },
      async loadReminderConfig() {
        return params.config ?? { orgId: "org_123" };
      },
    },
    async enqueueDelayedReminder(payload, delayMs) {
      enqueued.push({ payload, delayMs });
      return {
        queueName: "reminder-queue",
        jobId: `invoice:${payload.invoiceId}:reminder:${payload.reminderOffsetDays}:v1`,
        status: "queued",
      } satisfies QueuePublishResult;
    },
  };
}
