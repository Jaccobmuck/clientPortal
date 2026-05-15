import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { getReminderStatusDecision, shouldSendReminder } from "../reminders/statusPolicy.js";

describe("reminder status policy", () => {
  test("no-ops terminal and non-payable invoice states", () => {
    for (const status of ["paid", "void", "draft", "disputed"]) {
      assert.equal(getReminderStatusDecision(status), "noop");
      assert.equal(shouldSendReminder(status), false);
    }
  });

  test("allows payable invoice states", () => {
    for (const status of ["sent", "locked", "resolved", "overdue"]) {
      assert.equal(getReminderStatusDecision(status), "send");
      assert.equal(shouldSendReminder(status), true);
    }
  });

  test("treats unknown statuses as no-op", () => {
    assert.equal(getReminderStatusDecision("archived"), "noop");
  });

  test("normalizes status casing and whitespace", () => {
    assert.equal(getReminderStatusDecision(" SENT "), "send");
  });
});
