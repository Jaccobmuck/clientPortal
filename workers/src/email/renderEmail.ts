import type { InvoiceEmailViewModel } from "./viewModels.js";
import type { EmailType } from "./safety.js";
import { renderInvoiceSent, type RenderedEmail } from "./templates/invoiceSent.js";
import { renderPaymentReceived } from "./templates/paymentReceived.js";
import { renderPaymentConfirmed } from "./templates/paymentConfirmed.js";
import { renderOverdueReminder } from "./templates/overdueReminder.js";

export type { RenderedEmail };

const RENDERERS: Record<EmailType, (vm: InvoiceEmailViewModel) => RenderedEmail> = {
  invoice_sent: renderInvoiceSent,
  payment_received: renderPaymentReceived,
  payment_confirmed: renderPaymentConfirmed,
  overdue_reminder: renderOverdueReminder,
};

export function renderEmail(
  emailType: EmailType,
  vm: InvoiceEmailViewModel,
): RenderedEmail {
  const renderer = RENDERERS[emailType];
  if (!renderer) {
    throw new Error(`Unknown email type: ${emailType}`);
  }
  return renderer(vm);
}
