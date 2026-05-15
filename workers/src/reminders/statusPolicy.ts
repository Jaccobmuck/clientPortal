const NOOP_STATUSES = new Set(["paid", "void", "draft", "disputed"]);
const SENDABLE_STATUSES = new Set(["sent", "locked", "resolved", "overdue"]);

export type ReminderStatusDecision = "send" | "noop";

export function getReminderStatusDecision(status: string): ReminderStatusDecision {
  const normalized = normalizeStatus(status);

  if (NOOP_STATUSES.has(normalized)) {
    return "noop";
  }

  if (SENDABLE_STATUSES.has(normalized)) {
    return "send";
  }

  return "noop";
}

export function shouldSendReminder(status: string): boolean {
  return getReminderStatusDecision(status) === "send";
}

function normalizeStatus(status: string): string {
  return status.trim().toLowerCase();
}
