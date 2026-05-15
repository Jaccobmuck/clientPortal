import assert from "node:assert/strict";
import { test } from "node:test";

import {
  loadResendConfig,
  ResendConfigurationError,
} from "../email/resendClient.js";

// ── Resend config ──────────────────────────────────────────

test("loadResendConfig reads all env vars", () => {
  const config = loadResendConfig({
    RESEND_API_KEY: "re_test_123",
    RESEND_FROM_EMAIL: "Freelio <invoices@freelio.net>",
    RESEND_TEST_RECIPIENT_OVERRIDE: "dev@example.com",
  } as unknown as NodeJS.ProcessEnv);

  assert.equal(config.apiKey, "re_test_123");
  assert.equal(config.fromEmail, "Freelio <invoices@freelio.net>");
  assert.equal(config.testRecipientOverride, "dev@example.com");
});

test("loadResendConfig treats missing override as undefined", () => {
  const config = loadResendConfig({
    RESEND_API_KEY: "re_test_123",
    RESEND_FROM_EMAIL: "invoices@freelio.net",
  } as unknown as NodeJS.ProcessEnv);

  assert.equal(config.testRecipientOverride, undefined);
});

test("loadResendConfig trims whitespace", () => {
  const config = loadResendConfig({
    RESEND_API_KEY: "  re_test_123  ",
    RESEND_FROM_EMAIL: "  invoices@freelio.net  ",
    RESEND_TEST_RECIPIENT_OVERRIDE: "  dev@example.com  ",
  } as unknown as NodeJS.ProcessEnv);

  assert.equal(config.apiKey, "re_test_123");
  assert.equal(config.fromEmail, "invoices@freelio.net");
  assert.equal(config.testRecipientOverride, "dev@example.com");
});

test("loadResendConfig throws when RESEND_API_KEY is missing", () => {
  assert.throws(
    () =>
      loadResendConfig({
        RESEND_FROM_EMAIL: "invoices@freelio.net",
      } as unknown as NodeJS.ProcessEnv),
    (err) =>
      err instanceof ResendConfigurationError &&
      /RESEND_API_KEY/.test(err.message),
  );
});

test("loadResendConfig throws when RESEND_API_KEY is empty", () => {
  assert.throws(
    () =>
      loadResendConfig({
        RESEND_API_KEY: "   ",
        RESEND_FROM_EMAIL: "invoices@freelio.net",
      } as unknown as NodeJS.ProcessEnv),
    (err) =>
      err instanceof ResendConfigurationError &&
      /RESEND_API_KEY/.test(err.message),
  );
});

test("loadResendConfig throws when RESEND_FROM_EMAIL is missing", () => {
  assert.throws(
    () =>
      loadResendConfig({
        RESEND_API_KEY: "re_test_123",
      } as unknown as NodeJS.ProcessEnv),
    (err) =>
      err instanceof ResendConfigurationError &&
      /RESEND_FROM_EMAIL/.test(err.message),
  );
});
