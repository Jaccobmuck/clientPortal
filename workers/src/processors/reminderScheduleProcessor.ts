import type { Job, Processor } from "bullmq";

import { JOB_NAMES } from "../queues/constants.js";
import type { QueuePublishResult } from "../queues/publishers/invoiceQueuePublisher.js";
import { calculateReminderSchedule } from "../reminders/dateMath.js";
import { enqueueDelayedReminderJob } from "../reminders/publisher.js";
import {
  createSupabaseReminderDataSource,
  type ReminderDataSource,
} from "../reminders/repository.js";
import { enabledReminderRules } from "../reminders/rules.js";
import { shouldSendReminder } from "../reminders/statusPolicy.js";
import type { InvoiceReminderScheduleJob, InvoiceReminderSendJob } from "../types/jobs.js";

export type ReminderScheduleResult = {
  status: "scheduled" | "skipped";
  reason?: "invoice_not_found" | "org_not_found" | "status_noop" | "missing_due_date";
  scheduledCount: number;
  skippedPastCount: number;
  results: QueuePublishResult[];
};

export type ReminderScheduleProcessorDeps = {
  dataSource: ReminderDataSource;
  now: () => Date;
  enqueueDelayedReminder: (
    payload: InvoiceReminderSendJob,
    delayMs: number,
  ) => Promise<QueuePublishResult>;
};

export function createReminderScheduleProcessor(
  deps: Partial<ReminderScheduleProcessorDeps> = {},
): Processor<InvoiceReminderScheduleJob> {
  const resolvedDeps = reminderScheduleProcessorDeps(deps);

  return async (job: Job<InvoiceReminderScheduleJob>) => {
    if (job.name !== JOB_NAMES.INVOICE_REMINDER_SCHEDULE || !isScheduleJob(job.data)) {
      throw new Error("[reminder-queue] unsupported schedule reminder job.");
    }

    return processReminderScheduleJob(job.data, resolvedDeps);
  };
}

export async function processReminderScheduleJob(
  payload: InvoiceReminderScheduleJob,
  deps: ReminderScheduleProcessorDeps,
): Promise<ReminderScheduleResult> {
  if (!isScheduleJob(payload)) {
    throw new Error("Invalid reminder schedule payload.");
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
  if (!invoice.dueDate) {
    return skipped("missing_due_date");
  }

  const config = await deps.dataSource.loadReminderConfig({ orgId: payload.orgId });
  if (!config) {
    return skipped("org_not_found");
  }

  const rules = enabledReminderRules(config.ruleSource);
  const schedule = calculateReminderSchedule({
    dueDate: invoice.dueDate,
    rules,
    now: deps.now(),
    timezone: config.timezone,
  });

  const results = await Promise.all(
    schedule.map((entry) =>
      deps.enqueueDelayedReminder(
        {
          schemaVersion: 1,
          invoiceId: payload.invoiceId,
          orgId: payload.orgId,
          reminderOffsetDays: entry.offsetDays,
          scheduledFor: entry.scheduledFor,
          sendEventId: payload.sendEventId,
        },
        entry.delayMs,
      ),
    ),
  );

  return {
    status: "scheduled",
    scheduledCount: results.length,
    skippedPastCount: rules.length - schedule.length,
    results,
  };
}

function reminderScheduleProcessorDeps(
  deps: Partial<ReminderScheduleProcessorDeps>,
): ReminderScheduleProcessorDeps {
  return {
    dataSource: deps.dataSource ?? createSupabaseReminderDataSource(),
    now: deps.now ?? (() => new Date()),
    enqueueDelayedReminder: deps.enqueueDelayedReminder ?? enqueueDelayedReminderJob,
  };
}

function skipped(reason: ReminderScheduleResult["reason"]): ReminderScheduleResult {
  return {
    status: "skipped",
    reason,
    scheduledCount: 0,
    skippedPastCount: 0,
    results: [],
  };
}

function isScheduleJob(value: unknown): value is InvoiceReminderScheduleJob {
  if (!value || typeof value !== "object") {
    return false;
  }

  const data = value as Partial<InvoiceReminderScheduleJob>;
  return (
    data.schemaVersion === 1 &&
    typeof data.invoiceId === "string" &&
    typeof data.orgId === "string" &&
    (data.requestedByUserId === undefined || typeof data.requestedByUserId === "string") &&
    (data.sendEventId === undefined || typeof data.sendEventId === "string")
  );
}
