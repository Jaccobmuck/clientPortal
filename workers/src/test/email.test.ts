import assert from "node:assert/strict";
import { test } from "node:test";

import {
  loadResendConfig,
  ResendConfigurationError,
} from "../email/resendClient.js";
import {
  assertSupabaseConfigured,
  SupabaseConfigurationError,
} from "../email/supabaseClient.js";
import {
  formatCurrency,
  formatDate,
  buildPayUrl,
  buildViewModel,
  type InvoiceRow,
  type ClientRow,
  type OrgRow,
  type InvoiceEmailViewModel,
} from "../email/viewModels.js";
import { renderInvoiceSent } from "../email/templates/invoiceSent.js";
import { renderPaymentReceived } from "../email/templates/paymentReceived.js";
import { renderPaymentConfirmed } from "../email/templates/paymentConfirmed.js";
import { renderOverdueReminder } from "../email/templates/overdueReminder.js";
import {
  validateEmailSafety,
  validateRecipient,
  EmailSafetyError,
} from "../email/safety.js";

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

// ── Supabase config ────────────────────────────────────────

test("assertSupabaseConfigured reads env vars", () => {
  const config = assertSupabaseConfigured({
    SUPABASE_URL: "https://test.supabase.co",
    SUPABASE_SERVICE_ROLE_KEY: "eyJtest",
  } as unknown as NodeJS.ProcessEnv);

  assert.equal(config.url, "https://test.supabase.co");
  assert.equal(config.serviceRoleKey, "eyJtest");
});

test("assertSupabaseConfigured throws when SUPABASE_URL is missing", () => {
  assert.throws(
    () =>
      assertSupabaseConfigured({
        SUPABASE_SERVICE_ROLE_KEY: "eyJtest",
      } as unknown as NodeJS.ProcessEnv),
    (err) =>
      err instanceof SupabaseConfigurationError &&
      /SUPABASE_URL/.test(err.message),
  );
});

test("assertSupabaseConfigured throws when SUPABASE_SERVICE_ROLE_KEY is missing", () => {
  assert.throws(
    () =>
      assertSupabaseConfigured({
        SUPABASE_URL: "https://test.supabase.co",
      } as unknown as NodeJS.ProcessEnv),
    (err) =>
      err instanceof SupabaseConfigurationError &&
      /SUPABASE_SERVICE_ROLE_KEY/.test(err.message),
  );
});

// ── Format helpers ─────────────────────────────────────────

test("formatCurrency formats standard amounts", () => {
  assert.equal(formatCurrency("1250.00"), "$1,250.00");
  assert.equal(formatCurrency("0.50"), "$0.50");
  assert.equal(formatCurrency("99999.99"), "$99,999.99");
  assert.equal(formatCurrency("0"), "$0.00");
});

test("formatCurrency handles NaN gracefully", () => {
  assert.equal(formatCurrency("not-a-number"), "$0.00");
});

test("formatDate formats ISO dates", () => {
  assert.equal(formatDate("2026-01-15"), "January 15, 2026");
  assert.equal(formatDate("2026-06-01T12:00:00Z"), "June 1, 2026");
});

test("formatDate returns null for null or invalid input", () => {
  assert.equal(formatDate(null), null);
  assert.equal(formatDate("not-a-date"), null);
});

test("buildPayUrl constructs URL from token and frontend URL", () => {
  assert.equal(
    buildPayUrl("abc-123", "https://app.freelio.net"),
    "https://app.freelio.net/pay/abc-123",
  );
});

test("buildPayUrl strips trailing slashes from frontend URL", () => {
  assert.equal(
    buildPayUrl("abc-123", "https://app.freelio.net/"),
    "https://app.freelio.net/pay/abc-123",
  );
});

// ── View model ─────────────────────────────────────────────

const fakeInvoice: InvoiceRow = {
  id: "inv-001",
  org_id: "org-001",
  client_id: "client-001",
  invoice_number: "INV-2026-0001",
  status: "sent",
  pay_token: "tok-abc-123",
  due_date: "2026-02-15",
  issued_at: "2026-01-15T00:00:00Z",
  sent_at: "2026-01-15T10:00:00Z",
  paid_at: null,
  subtotal: "1000.00",
  tax_rate: "0.0800",
  tax_amount: "80.00",
  total: "1080.00",
  notes: "Test invoice",
};

const fakeClient: ClientRow = {
  id: "client-001",
  name: "Acme Corp",
  email: "billing@acme.com",
  company: "Acme Corporation",
};

const fakeOrg: OrgRow = {
  id: "org-001",
  name: "Freelio Studio",
  slug: "freelio-studio",
};

test("buildViewModel assembles all fields correctly", () => {
  const vm = buildViewModel({
    invoice: fakeInvoice,
    client: fakeClient,
    org: fakeOrg,
    frontendUrl: "https://app.freelio.net",
    reminderOffsetDays: 7,
  });

  assert.equal(vm.invoiceNumber, "INV-2026-0001");
  assert.equal(vm.invoiceStatus, "sent");
  assert.equal(vm.clientName, "Acme Corp");
  assert.equal(vm.clientEmail, "billing@acme.com");
  assert.equal(vm.clientCompany, "Acme Corporation");
  assert.equal(vm.orgName, "Freelio Studio");
  assert.equal(vm.totalFormatted, "$1,080.00");
  assert.equal(vm.subtotalFormatted, "$1,000.00");
  assert.equal(vm.taxFormatted, "$80.00");
  assert.equal(vm.dueDateFormatted, "February 15, 2026");
  assert.equal(vm.issuedAtFormatted, "January 15, 2026");
  assert.equal(vm.paidAtFormatted, null);
  assert.equal(vm.payUrl, "https://app.freelio.net/pay/tok-abc-123");
  assert.equal(vm.reminderOffsetDays, 7);
});

test("buildViewModel defaults reminderOffsetDays to undefined", () => {
  const vm = buildViewModel({
    invoice: fakeInvoice,
    client: fakeClient,
    org: fakeOrg,
    frontendUrl: "https://app.freelio.net",
  });

  assert.equal(vm.reminderOffsetDays, undefined);
});

// ── Shared test view model ─────────────────────────────────

function createTestViewModel(overrides: Partial<InvoiceEmailViewModel> = {}): InvoiceEmailViewModel {
  return {
    invoiceNumber: "INV-2026-0001",
    invoiceStatus: "sent",
    clientName: "Acme Corp",
    clientEmail: "billing@acme.com",
    clientCompany: "Acme Corporation",
    orgName: "Freelio Studio",
    totalFormatted: "$1,080.00",
    subtotalFormatted: "$1,000.00",
    taxFormatted: "$80.00",
    dueDateFormatted: "February 15, 2026",
    issuedAtFormatted: "January 15, 2026",
    paidAtFormatted: null,
    payUrl: "https://app.freelio.net/pay/tok-abc-123",
    reminderOffsetDays: undefined,
    ...overrides,
  };
}

// ── invoice_sent template ──────────────────────────────────

test("renderInvoiceSent renders without throwing", () => {
  const result = renderInvoiceSent(createTestViewModel());
  assert.ok(result.subject);
  assert.ok(result.html);
  assert.ok(result.text);
});

test("renderInvoiceSent subject contains invoice number and org name", () => {
  const result = renderInvoiceSent(createTestViewModel());
  assert.ok(result.subject.includes("INV-2026-0001"));
  assert.ok(result.subject.includes("Freelio Studio"));
});

test("renderInvoiceSent HTML contains pay URL", () => {
  const result = renderInvoiceSent(createTestViewModel());
  assert.ok(result.html.includes("https://app.freelio.net/pay/tok-abc-123"));
});

test("renderInvoiceSent text contains pay URL", () => {
  const result = renderInvoiceSent(createTestViewModel());
  assert.ok(result.text.includes("https://app.freelio.net/pay/tok-abc-123"));
});

test("renderInvoiceSent includes due date when present", () => {
  const result = renderInvoiceSent(createTestViewModel());
  assert.ok(result.html.includes("February 15, 2026"));
});

test("renderInvoiceSent omits due date when null", () => {
  const result = renderInvoiceSent(createTestViewModel({ dueDateFormatted: null }));
  assert.ok(!result.html.includes("Due:"));
});

// ── payment_received template ──────────────────────────────

test("renderPaymentReceived renders without throwing", () => {
  const result = renderPaymentReceived(createTestViewModel());
  assert.ok(result.subject);
  assert.ok(result.html);
  assert.ok(result.text);
});

test("renderPaymentReceived subject contains invoice number", () => {
  const result = renderPaymentReceived(createTestViewModel());
  assert.ok(result.subject.includes("INV-2026-0001"));
});

test("renderPaymentReceived does not contain pay URL", () => {
  const result = renderPaymentReceived(createTestViewModel());
  assert.ok(!result.html.includes("View &amp; Pay"));
  assert.ok(!result.html.includes("/pay/tok-abc-123"));
});

// ── payment_confirmed template ─────────────────────────────

test("renderPaymentConfirmed renders without throwing", () => {
  const result = renderPaymentConfirmed(createTestViewModel({ paidAtFormatted: "January 20, 2026" }));
  assert.ok(result.subject);
  assert.ok(result.html);
  assert.ok(result.text);
});

test("renderPaymentConfirmed subject contains invoice number", () => {
  const result = renderPaymentConfirmed(createTestViewModel());
  assert.ok(result.subject.includes("INV-2026-0001"));
});

test("renderPaymentConfirmed does not contain pay URL", () => {
  const result = renderPaymentConfirmed(createTestViewModel());
  assert.ok(!result.html.includes("View &amp; Pay"));
  assert.ok(!result.html.includes("/pay/tok-abc-123"));
});

test("renderPaymentConfirmed includes paid date when present", () => {
  const result = renderPaymentConfirmed(createTestViewModel({ paidAtFormatted: "January 20, 2026" }));
  assert.ok(result.html.includes("January 20, 2026"));
});

// ── overdue_reminder template ──────────────────────────────

test("renderOverdueReminder renders without throwing", () => {
  const result = renderOverdueReminder(createTestViewModel({ reminderOffsetDays: 7 }));
  assert.ok(result.subject);
  assert.ok(result.html);
  assert.ok(result.text);
});

test("renderOverdueReminder subject contains invoice number", () => {
  const result = renderOverdueReminder(createTestViewModel());
  assert.ok(result.subject.includes("INV-2026-0001"));
  assert.ok(result.subject.includes("overdue"));
});

test("renderOverdueReminder HTML contains pay URL", () => {
  const result = renderOverdueReminder(createTestViewModel());
  assert.ok(result.html.includes("https://app.freelio.net/pay/tok-abc-123"));
});

test("renderOverdueReminder mentions offset days when present", () => {
  const result = renderOverdueReminder(createTestViewModel({ reminderOffsetDays: 7 }));
  assert.ok(result.html.includes("7 days past due"));
});

test("renderOverdueReminder uses singular day for offset 1", () => {
  const result = renderOverdueReminder(createTestViewModel({ reminderOffsetDays: 1 }));
  assert.ok(result.html.includes("1 day past due"));
});

test("renderOverdueReminder omits offset note when undefined", () => {
  const result = renderOverdueReminder(createTestViewModel({ reminderOffsetDays: undefined }));
  assert.ok(!result.html.includes("past due"));
});

// ── Email safety rules ─────────────────────────────────────

test("validateEmailSafety allows invoice_sent for sent status", () => {
  assert.doesNotThrow(() => validateEmailSafety("invoice_sent", "sent"));
});

test("validateEmailSafety allows invoice_sent for locked status", () => {
  assert.doesNotThrow(() => validateEmailSafety("invoice_sent", "locked"));
});

test("validateEmailSafety rejects invoice_sent for draft", () => {
  assert.throws(
    () => validateEmailSafety("invoice_sent", "draft"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateEmailSafety rejects invoice_sent for void", () => {
  assert.throws(
    () => validateEmailSafety("invoice_sent", "void"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateEmailSafety rejects invoice_sent for paid", () => {
  assert.throws(
    () => validateEmailSafety("invoice_sent", "paid"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateEmailSafety allows payment_received for sent", () => {
  assert.doesNotThrow(() => validateEmailSafety("payment_received", "sent"));
});

test("validateEmailSafety allows payment_received for locked", () => {
  assert.doesNotThrow(() => validateEmailSafety("payment_received", "locked"));
});

test("validateEmailSafety allows payment_received for paid", () => {
  assert.doesNotThrow(() => validateEmailSafety("payment_received", "paid"));
});

test("validateEmailSafety allows payment_confirmed for paid", () => {
  assert.doesNotThrow(() => validateEmailSafety("payment_confirmed", "paid"));
});

test("validateEmailSafety rejects payment_confirmed for sent", () => {
  assert.throws(
    () => validateEmailSafety("payment_confirmed", "sent"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateEmailSafety allows overdue_reminder for sent", () => {
  assert.doesNotThrow(() => validateEmailSafety("overdue_reminder", "sent"));
});

test("validateEmailSafety allows overdue_reminder for overdue", () => {
  assert.doesNotThrow(() => validateEmailSafety("overdue_reminder", "overdue"));
});

test("validateEmailSafety rejects overdue_reminder for paid", () => {
  assert.throws(
    () => validateEmailSafety("overdue_reminder", "paid"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateEmailSafety rejects overdue_reminder for void", () => {
  assert.throws(
    () => validateEmailSafety("overdue_reminder", "void"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateEmailSafety rejects overdue_reminder for draft", () => {
  assert.throws(
    () => validateEmailSafety("overdue_reminder", "draft"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateEmailSafety rejects overdue_reminder for disputed", () => {
  assert.throws(
    () => validateEmailSafety("overdue_reminder", "disputed"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

// ── Recipient validation ───────────────────────────────────

test("validateRecipient accepts valid email", () => {
  assert.doesNotThrow(() => validateRecipient("test@example.com"));
});

test("validateRecipient rejects null", () => {
  assert.throws(
    () => validateRecipient(null),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateRecipient rejects undefined", () => {
  assert.throws(
    () => validateRecipient(undefined),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateRecipient rejects empty string", () => {
  assert.throws(
    () => validateRecipient(""),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});

test("validateRecipient rejects missing domain dot", () => {
  assert.throws(
    () => validateRecipient("test@localhost"),
    (err) => err instanceof EmailSafetyError && err.permanent === true,
  );
});
