import { Worker, UnrecoverableError, type Job } from "bullmq";

import { QUEUE_NAMES } from "../queues/constants.js";
import type { EmailQueueJob } from "../queues/factory.js";
import { getSharedRedisConnection } from "../queues/redis.js";
import type { InvoiceEmailJob, SmokeQueueJob } from "../types/jobs.js";
import {
  loadResendConfig,
  sendEmail,
  type ResendConfig,
} from "../email/resendClient.js";
import { getWorkerSupabaseClient } from "../email/supabaseClient.js";
import {
  buildViewModel,
  type InvoiceRow,
  type ClientRow,
  type OrgRow,
} from "../email/viewModels.js";
import { renderEmail } from "../email/renderEmail.js";
import {
  validateEmailSafety,
  validateRecipient,
  EmailSafetyError,
  type EmailType,
} from "../email/safety.js";
import { hasAlreadySent, recordEmailSent } from "../email/notificationLog.js";

function assertFrontendUrl(env: NodeJS.ProcessEnv = process.env): string {
  const url = env.FRONTEND_URL?.trim();
  if (!url) {
    throw new UnrecoverableError("FRONTEND_URL is required for the email worker.");
  }
  return url;
}

function isSmokeJob(data: EmailQueueJob): data is SmokeQueueJob {
  return "smoke" in data && (data as SmokeQueueJob).smoke === true;
}

function isEmailJob(data: EmailQueueJob): data is InvoiceEmailJob {
  return "emailType" in data && !isSmokeJob(data);
}

const EMAIL_TYPES = new Set<string>([
  "invoice_sent",
  "payment_received",
  "payment_confirmed",
  "overdue_reminder",
]);

async function processEmailJob(job: Job<EmailQueueJob>): Promise<void> {
  if (isSmokeJob(job.data)) {
    console.log(`[${QUEUE_NAMES.EMAIL}] smoke job completed`, {
      jobId: job.id,
      correlationId: job.data.correlationId,
    });
    return;
  }

  if (!isEmailJob(job.data)) {
    throw new UnrecoverableError("Invalid job payload: not an email or smoke job");
  }

  const data = job.data;

  if (data.schemaVersion !== 1) {
    throw new UnrecoverableError(
      `Unsupported schemaVersion: ${data.schemaVersion}`,
    );
  }

  if (!data.invoiceId || !data.orgId || !data.emailType) {
    throw new UnrecoverableError(
      "Missing required fields: invoiceId, orgId, emailType",
    );
  }

  if (!EMAIL_TYPES.has(data.emailType)) {
    throw new UnrecoverableError(`Unknown emailType: ${data.emailType}`);
  }

  const emailType = data.emailType as EmailType;

  const supabase = getWorkerSupabaseClient();
  const resendConfig = loadResendConfig();
  const frontendUrl = assertFrontendUrl();

  const [invoiceResult, clientResult, orgResult] = await loadInvoiceData(
    supabase,
    data.invoiceId,
    data.orgId,
  );

  if (!invoiceResult) {
    throw new UnrecoverableError(
      `Invoice not found: ${data.invoiceId} in org ${data.orgId}`,
    );
  }

  if (!clientResult) {
    throw new UnrecoverableError(
      `Client not found for invoice: ${data.invoiceId}`,
    );
  }

  if (!orgResult) {
    throw new UnrecoverableError(`Organization not found: ${data.orgId}`);
  }

  try {
    validateEmailSafety(emailType, invoiceResult.status);
  } catch (err) {
    if (err instanceof EmailSafetyError && err.permanent) {
      throw new UnrecoverableError(err.message);
    }
    throw err;
  }

  try {
    validateRecipient(clientResult.email);
  } catch (err) {
    if (err instanceof EmailSafetyError && err.permanent) {
      throw new UnrecoverableError(err.message);
    }
    throw err;
  }

  const vm = buildViewModel({
    invoice: invoiceResult,
    client: clientResult,
    org: orgResult,
    frontendUrl,
    reminderOffsetDays: data.reminderOffsetDays,
  });

  const rendered = renderEmail(emailType, vm);

  const alreadySent = await hasAlreadySent(supabase, {
    orgId: data.orgId,
    invoiceId: data.invoiceId,
    emailType,
    reminderOffsetDays: data.reminderOffsetDays,
  });

  if (alreadySent) {
    console.log(`[${QUEUE_NAMES.EMAIL}] duplicate skipped`, {
      jobId: job.id,
      invoiceId: data.invoiceId,
      emailType,
    });
    return;
  }

  const recipient = resendConfig.testRecipientOverride ?? clientResult.email;

  const result = await sendEmail(resendConfig, {
    from: resendConfig.fromEmail,
    to: [recipient],
    subject: rendered.subject,
    html: rendered.html,
    text: rendered.text,
  });

  if (!result.ok) {
    if (result.retryable) {
      throw new Error(
        `Resend API error (${result.statusCode}): ${result.error}`,
      );
    }
    throw new UnrecoverableError(
      `Resend API permanent error (${result.statusCode}): ${result.error}`,
    );
  }

  await recordEmailSent(supabase, {
    orgId: data.orgId,
    invoiceId: data.invoiceId,
    emailType,
    recipientEmail: recipient,
    resendMessageId: result.messageId,
    jobId: job.id ?? "unknown",
    reminderOffsetDays: data.reminderOffsetDays,
  });

  console.log(`[${QUEUE_NAMES.EMAIL}] email sent`, {
    jobId: job.id,
    invoiceId: data.invoiceId,
    emailType,
    messageId: result.messageId,
  });
}

async function loadInvoiceData(
  supabase: ReturnType<typeof getWorkerSupabaseClient>,
  invoiceId: string,
  orgId: string,
): Promise<[InvoiceRow | null, ClientRow | null, OrgRow | null]> {
  const { data: invoice, error: invoiceError } = await supabase
    .from("invoices")
    .select(
      "id, org_id, client_id, invoice_number, status, pay_token, due_date, issued_at, sent_at, paid_at, subtotal, tax_rate, tax_amount, total, notes",
    )
    .eq("id", invoiceId)
    .eq("org_id", orgId)
    .single();

  if (invoiceError || !invoice) {
    return [null, null, null];
  }

  const typedInvoice = invoice as unknown as InvoiceRow;

  const [clientResult, orgResult] = await Promise.all([
    supabase
      .from("clients")
      .select("id, name, email, company")
      .eq("id", typedInvoice.client_id)
      .eq("org_id", orgId)
      .is("deleted_at", null)
      .single(),
    supabase
      .from("organizations")
      .select("id, name, slug")
      .eq("id", orgId)
      .single(),
  ]);

  return [
    typedInvoice,
    clientResult.error ? null : (clientResult.data as unknown as ClientRow),
    orgResult.error ? null : (orgResult.data as unknown as OrgRow),
  ];
}

export function createEmailWorker(): Worker<EmailQueueJob> {
  return new Worker<EmailQueueJob>(
    QUEUE_NAMES.EMAIL,
    processEmailJob,
    { connection: getSharedRedisConnection() },
  );
}
