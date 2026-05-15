import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  calculateReminderSchedule,
  calculateScheduledReminderDate,
} from "../reminders/dateMath.js";

describe("reminder date math", () => {
  test("uses due date plus offset at 9 AM UTC when no timezone exists", () => {
    const scheduled = calculateScheduledReminderDate({
      dueDate: "2026-05-10",
      offsetDays: 3,
    });

    assert.equal(scheduled.toISOString(), "2026-05-13T09:00:00.000Z");
  });

  test("uses 9 AM in the supplied org timezone", () => {
    const scheduled = calculateScheduledReminderDate({
      dueDate: "2026-05-10",
      offsetDays: 0,
      timezone: "America/Los_Angeles",
    });

    assert.equal(scheduled.toISOString(), "2026-05-10T16:00:00.000Z");
  });

  test("filters reminders scheduled in the past", () => {
    const schedule = calculateReminderSchedule({
      dueDate: "2026-05-10",
      now: new Date("2026-05-10T10:00:00.000Z"),
      rules: [
        { offsetDays: 0, enabled: true },
        { offsetDays: 1, enabled: true },
      ],
    });

    assert.deepEqual(schedule, [
      {
        offsetDays: 1,
        scheduledFor: "2026-05-11T09:00:00.000Z",
        delayMs: 82_800_000,
      },
    ]);
  });

  test("returns BullMQ delays in milliseconds", () => {
    const schedule = calculateReminderSchedule({
      dueDate: "2026-05-10",
      now: new Date("2026-05-10T08:59:30.000Z"),
      rules: [{ offsetDays: 0, enabled: true }],
    });

    assert.equal(schedule[0]?.delayMs, 30_000);
  });

  test("skips disabled rules", () => {
    const schedule = calculateReminderSchedule({
      dueDate: "2026-05-10",
      now: new Date("2026-05-10T08:00:00.000Z"),
      rules: [{ offsetDays: 0, enabled: false }],
    });

    assert.deepEqual(schedule, []);
  });

  test("rejects invalid due dates", () => {
    assert.throws(
      () => calculateScheduledReminderDate({ dueDate: "2026-02-30", offsetDays: 0 }),
      /valid calendar date/,
    );
  });
});
