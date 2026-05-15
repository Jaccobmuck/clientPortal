import assert from "node:assert/strict";
import { describe, test } from "node:test";

import type { QueuePublishResult } from "../queues/publishers/invoiceQueuePublisher.js";
import {
  processReminderSendJob,
  type ReminderSendProcessorDeps,
} from "../processors/reminderSendProcessor.js";
import type { ReminderInvoice } from "../reminders/repository.js";
import type { InvoiceReminderSendJob } from "../types/jobs.js";

const SEND_PAYLOAD = {
  schemaVersion: 1,
  invoiceId: "inv_123",
  orgId: "org_123",
  reminderOffsetDays: 7,
  scheduledFor: "2026-05-17T09:00:00.000Z",
  sendEventId: "send_123",
} satisfies InvoiceReminderSendJob;

describe("reminder send processor", () => {
  test("reloads invoice fresh before enqueuing overdue reminder email", async () => {
    const deps = fakeDeps({
      invoice: {
        id: "inv_123",
        orgId: "org_123",
        status: "sent",
        dueDate: "2026-05-10",
      },
    });

    const result = await processReminderSendJob(SEND_PAYLOAD, deps);

    assert.equal(result.status, "queued");
    assert.equal(result.result?.queueName, "email-queue");
    assert.deepEqual(deps.emailPayloads, [SEND_PAYLOAD]);
  });

  test("no-ops if the invoice became paid before the delayed job fired", async () => {
    const deps = fakeDeps({
      invoice: {
        id: "inv_123",
        orgId: "org_123",
        status: "paid",
        dueDate: "2026-05-10",
      },
    });

    const result = await processReminderSendJob(SEND_PAYLOAD, deps);

    assert.equal(result.status, "skipped");
    assert.equal(result.reason, "status_noop");
    assert.equal(deps.emailPayloads.length, 0);
  });

  test("no-ops if the invoice no longer exists", async () => {
    const deps = fakeDeps({ invoice: null });

    const result = await processReminderSendJob(SEND_PAYLOAD, deps);

    assert.equal(result.status, "skipped");
    assert.equal(result.reason, "invoice_not_found");
  });

  test("rejects malformed send payloads", async () => {
    const deps = fakeDeps({ invoice: null });

    await assert.rejects(
      () =>
        processReminderSendJob(
          { ...SEND_PAYLOAD, reminderOffsetDays: 1.5 },
          deps,
        ),
      /Invalid reminder send payload/,
    );
  });
});

function fakeDeps(params: { invoice?: ReminderInvoice | null }): ReminderSendProcessorDeps & {
  emailPayloads: InvoiceReminderSendJob[];
} {
  const emailPayloads: InvoiceReminderSendJob[] = [];

  return {
    emailPayloads,
    dataSource: {
      async loadInvoice() {
        return params.invoice ?? null;
      },
      async loadReminderConfig() {
        return { orgId: "org_123" };
      },
    },
    async enqueueOverdueReminderEmail(payload) {
      emailPayloads.push(payload);
      return {
        queueName: "email-queue",
        jobId: `invoice:${payload.invoiceId}:overdue-reminder:${payload.reminderOffsetDays}:v1`,
        status: "queued",
      } satisfies QueuePublishResult;
    },
  };
}
