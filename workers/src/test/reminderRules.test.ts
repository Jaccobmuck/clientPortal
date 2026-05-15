import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  DEFAULT_REMINDER_RULES,
  enabledReminderRules,
  loadReminderScheduleRules,
} from "../reminders/rules.js";

describe("reminder rule loading", () => {
  test("uses the default schedule when no source exists", () => {
    assert.deepEqual(loadReminderScheduleRules(undefined), DEFAULT_REMINDER_RULES);
  });

  test("normalizes snake_case and camelCase offsets", () => {
    const rules = loadReminderScheduleRules([
      { offset_days: 3, enabled: true },
      { offsetDays: -1, enabled: false },
    ]);

    assert.deepEqual(rules, [
      { offsetDays: -1, enabled: false },
      { offsetDays: 3, enabled: true },
    ]);
  });

  test("filters malformed rules and keeps valid ones", () => {
    assert.deepEqual(loadReminderScheduleRules([{ offset_days: "7" }, { enabled: true }]), [
      { offsetDays: 7, enabled: true },
    ]);
  });

  test("falls back to defaults when every provided rule is invalid", () => {
    assert.deepEqual(loadReminderScheduleRules([{ offset_days: 1.5 }]), DEFAULT_REMINDER_RULES);
  });

  test("returns only enabled rules for scheduling", () => {
    assert.deepEqual(
      enabledReminderRules([
        { offset_days: -3, enabled: true },
        { offset_days: 0, enabled: false },
      ]),
      [{ offsetDays: -3, enabled: true }],
    );
  });
});
