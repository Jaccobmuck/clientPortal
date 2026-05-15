import type { Job, Processor } from "bullmq";

import { JOB_NAMES } from "../queues/constants.js";
import type { QueuePublishResult } from "../queues/publishers/invoiceQueuePublisher.js";
import { enqueueOverdueReminderEmailJob } from "../reminders/publisher.js";
import {
  createSupabaseReminderDataSource,
  type ReminderDataSource,
} from "../reminders/repository.js";
import { shouldSendReminder } from "../reminders/statusPolicy.js";
import type { InvoiceReminderSendJob } from "../types/jobs.js";

export type ReminderSendResult = {
  status: "queued" | "skipped";
  reason?: "invoice_not_found" | "status_noop";
  result?: QueuePublishResult;
};

export type ReminderSendProcessorDeps = {
  dataSource: ReminderDataSource;
  enqueueOverdueReminderEmail: (
    payload: InvoiceReminderSendJob,
  ) => Promise<QueuePublishResult>;
};

export function createReminderSendProcessor(
  deps: Partial<ReminderSendProcessorDeps> = {},
): Processor<InvoiceReminderSendJob> {
  const resolvedDeps = reminderSendProcessorDeps(deps);

  return async (job: Job<InvoiceReminderSendJob>) => {
    if (job.name !== JOB_NAMES.INVOICE_REMINDER_SEND || !isSendJob(job.data)) {
      throw new Error("[reminder-queue] unsupported send reminder job.");
    }

    return processReminderSendJob(job.data, resolvedDeps);
  };
}

export async function processReminderSendJob(
  payload: InvoiceReminderSendJob,
  deps: ReminderSendProcessorDeps,
): Promise<ReminderSendResult> {
  if (!isSendJob(payload)) {
    throw new Error("Invalid reminder send payload.");
  }

  const invoice = await deps.dataSource.loadInvoice({
    invoiceId: payload.invoiceId,
    orgId: payload.orgId,
  });
  if (!invoice) {
    return skipped("invoice_not_found");
  }
  if (!shouldSendReminder(invoice.status)) {
    return skipped("status_noop");
  }

  const result = await deps.enqueueOverdueReminderEmail(payload);
  return {
    status: "queued",
    result,
  };
}

function reminderSendProcessorDeps(
  deps: Partial<ReminderSendProcessorDeps>,
): ReminderSendProcessorDeps {
  return {
    dataSource: deps.dataSource ?? createSupabaseReminderDataSource(),
    enqueueOverdueReminderEmail:
      deps.enqueueOverdueReminderEmail ?? enqueueOverdueReminderEmailJob,
  };
}

function skipped(reason: ReminderSendResult["reason"]): ReminderSendResult {
  return { status: "skipped", reason };
}

function isSendJob(value: unknown): value is InvoiceReminderSendJob {
  if (!value || typeof value !== "object") {
    return false;
  }

  const data = value as Partial<InvoiceReminderSendJob>;
  return (
    data.schemaVersion === 1 &&
    typeof data.invoiceId === "string" &&
    typeof data.orgId === "string" &&
    Number.isInteger(data.reminderOffsetDays) &&
    typeof data.scheduledFor === "string" &&
    (data.sendEventId === undefined || typeof data.sendEventId === "string")
  );
}
