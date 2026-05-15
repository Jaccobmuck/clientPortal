import type { EmailType } from "./safety.js";
import { renderEmail, type RenderedEmail } from "./renderEmail.js";
import {
  sendEmail,
  type ResendConfig,
  type ResendSendResult,
} from "./resendClient.js";
import type { InvoiceEmailViewModel } from "./viewModels.js";

const EMAIL_TYPES: EmailType[] = [
  "invoice_sent",
  "payment_received",
  "payment_confirmed",
  "overdue_reminder",
];

export function createFakeViewModel(
  overrides: Partial<InvoiceEmailViewModel> = {},
): InvoiceEmailViewModel {
  return {
    invoiceNumber: "SMOKE-001",
    invoiceStatus: "sent",
    clientName: "Smoke Test Client",
    clientEmail: "smoke@example.com",
    clientCompany: "Smoke Test Inc.",
    orgName: "Freelio Smoke",
    totalFormatted: "$1,234.56",
    subtotalFormatted: "$1,140.33",
    taxFormatted: "$94.23",
    dueDateFormatted: "December 31, 2026",
    issuedAtFormatted: "December 1, 2026",
    paidAtFormatted: null,
    payUrl: "https://example.com/pay/00000000-0000-0000-0000-000000000000",
    reminderOffsetDays: undefined,
    ...overrides,
  };
}

export function renderAllTemplates(
  vm?: InvoiceEmailViewModel,
): Record<EmailType, RenderedEmail> {
  const viewModel = vm ?? createFakeViewModel();

  return Object.fromEntries(
    EMAIL_TYPES.map((type) => [type, renderEmail(type, viewModel)]),
  ) as Record<EmailType, RenderedEmail>;
}

export async function sendSmokeEmail(params: {
  config: ResendConfig;
  emailType: EmailType;
  recipientOverride: string;
}): Promise<ResendSendResult> {
  const vm = createFakeViewModel();
  const rendered = renderEmail(params.emailType, vm);

  return sendEmail(params.config, {
    from: params.config.fromEmail,
    to: [params.recipientOverride],
    subject: `[SMOKE TEST] ${rendered.subject}`,
    html: rendered.html,
    text: rendered.text,
  });
}
