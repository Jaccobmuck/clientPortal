import type { ReminderScheduleRule } from "./rules.js";

const DEFAULT_SEND_HOUR = 9;
const DEFAULT_TIMEZONE = "UTC";
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

export type ReminderScheduleEntry = {
  offsetDays: number;
  scheduledFor: string;
  delayMs: number;
};

export function calculateReminderSchedule(params: {
  dueDate: string;
  rules: ReminderScheduleRule[];
  now: Date;
  timezone?: string | null;
}): ReminderScheduleEntry[] {
  return params.rules
    .filter((rule) => rule.enabled)
    .map((rule) => {
      const scheduledFor = calculateScheduledReminderDate({
        dueDate: params.dueDate,
        offsetDays: rule.offsetDays,
        timezone: params.timezone,
      });
      const delayMs = scheduledFor.getTime() - params.now.getTime();

      return {
        offsetDays: rule.offsetDays,
        scheduledFor: scheduledFor.toISOString(),
        delayMs,
      };
    })
    .filter((entry) => entry.delayMs > 0)
    .sort((a, b) => a.delayMs - b.delayMs);
}

export function calculateScheduledReminderDate(params: {
  dueDate: string;
  offsetDays: number;
  timezone?: string | null;
}): Date {
  if (!Number.isInteger(params.offsetDays)) {
    throw new Error("offsetDays must be an integer.");
  }

  const targetDate = addDays(parseIsoDate(params.dueDate), params.offsetDays);
  const timezone = params.timezone?.trim() || DEFAULT_TIMEZONE;

  return zonedDateTimeToUtc({
    ...targetDate,
    hour: DEFAULT_SEND_HOUR,
    minute: 0,
    second: 0,
    millisecond: 0,
    timezone,
  });
}

function parseIsoDate(value: string): { year: number; month: number; day: number } {
  const match = DATE_RE.exec(value);
  if (!match) {
    throw new Error("dueDate must be an ISO date string.");
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    throw new Error("dueDate must be a valid calendar date.");
  }

  return { year, month, day };
}

function addDays(
  date: { year: number; month: number; day: number },
  days: number,
): { year: number; month: number; day: number } {
  const shifted = new Date(Date.UTC(date.year, date.month - 1, date.day + days));
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
  };
}

function zonedDateTimeToUtc(params: {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  millisecond: number;
  timezone: string;
}): Date {
  const localAsUtc = Date.UTC(
    params.year,
    params.month - 1,
    params.day,
    params.hour,
    params.minute,
    params.second,
    params.millisecond,
  );

  if (params.timezone === DEFAULT_TIMEZONE) {
    return new Date(localAsUtc);
  }

  let utcMs = localAsUtc;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const offsetMs = getTimeZoneOffsetMs(params.timezone, utcMs);
    const nextUtcMs = localAsUtc - offsetMs;

    if (nextUtcMs === utcMs) {
      return new Date(nextUtcMs);
    }

    utcMs = nextUtcMs;
  }

  return new Date(utcMs);
}

function getTimeZoneOffsetMs(timezone: string, instantMs: number): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(instantMs));

  const values = Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, Number(part.value)]),
  );

  return (
    Date.UTC(
      values.year,
      values.month - 1,
      values.day,
      values.hour,
      values.minute,
      values.second,
    ) - instantMs
  );
}
