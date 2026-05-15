import type { InvoiceEmailViewModel } from "../viewModels.js";
import type { RenderedEmail } from "./invoiceSent.js";

export function renderPaymentReceived(vm: InvoiceEmailViewModel): RenderedEmail {
  const subject = `Payment received for Invoice ${vm.invoiceNumber}`;

  const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;max-width:600px;margin:0 auto;padding:20px;">
  <h2 style="margin:0 0 24px;color:#1a1a1a;">Payment Received</h2>
  <p style="margin:0 0 8px;">Hi ${vm.clientName},</p>
  <p style="margin:0 0 16px;">We received your payment of <strong>${vm.totalFormatted}</strong> for invoice <strong>${vm.invoiceNumber}</strong>.</p>
  <p style="margin:0 0 16px;color:#555;">Your payment is being processed. You will receive a confirmation once it has been fully cleared.</p>
  <table style="width:100%;border-collapse:collapse;margin:0 0 16px;">
    <tr><td style="padding:8px 0;color:#555;">Invoice</td><td style="padding:8px 0;text-align:right;font-weight:600;">${vm.invoiceNumber}</td></tr>
    <tr><td style="padding:8px 0;color:#555;">Amount</td><td style="padding:8px 0;text-align:right;font-weight:600;">${vm.totalFormatted}</td></tr>
  </table>
  <hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0 16px;">
  <p style="margin:0;font-size:13px;color:#888;">${vm.orgName}</p>
</body>
</html>`;

  const text = `Payment Received

Hi ${vm.clientName},

We received your payment of ${vm.totalFormatted} for invoice ${vm.invoiceNumber}.

Your payment is being processed. You will receive a confirmation once it has been fully cleared.

Invoice: ${vm.invoiceNumber}
Amount: ${vm.totalFormatted}

${vm.orgName}`;

  return { subject, html, text };
}
