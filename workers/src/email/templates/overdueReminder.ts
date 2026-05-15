import type { InvoiceEmailViewModel } from "../viewModels.js";
import type { RenderedEmail } from "./invoiceSent.js";

export function renderOverdueReminder(vm: InvoiceEmailViewModel): RenderedEmail {
  const subject = `Reminder: Invoice ${vm.invoiceNumber} is overdue`;

  const offsetNote =
    vm.reminderOffsetDays != null
      ? `<p style="margin:0 0 16px;color:#b91c1c;">This invoice is ${vm.reminderOffsetDays} day${vm.reminderOffsetDays === 1 ? "" : "s"} past due.</p>`
      : "";

  const offsetText =
    vm.reminderOffsetDays != null
      ? `This invoice is ${vm.reminderOffsetDays} day${vm.reminderOffsetDays === 1 ? "" : "s"} past due.\n\n`
      : "";

  const dueLine = vm.dueDateFormatted
    ? `<tr><td style="padding:8px 0;color:#555;">Due date</td><td style="padding:8px 0;text-align:right;font-weight:600;">${vm.dueDateFormatted}</td></tr>`
    : "";

  const dueText = vm.dueDateFormatted ? `Due date: ${vm.dueDateFormatted}\n` : "";

  const payButton = vm.payUrl
    ? `<p style="margin:24px 0;"><a href="${vm.payUrl}" style="display:inline-block;padding:12px 24px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:600;">View &amp; Pay Invoice</a></p>`
    : "";

  const payLinkText = vm.payUrl ? `\nView & pay your invoice: ${vm.payUrl}\n` : "";

  const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;max-width:600px;margin:0 auto;padding:20px;">
  <h2 style="margin:0 0 24px;color:#b91c1c;">Payment Reminder</h2>
  <p style="margin:0 0 8px;">Hi ${vm.clientName},</p>
  <p style="margin:0 0 16px;">This is a friendly reminder that invoice <strong>${vm.invoiceNumber}</strong> for <strong>${vm.totalFormatted}</strong> is overdue.</p>
  ${offsetNote}
  <table style="width:100%;border-collapse:collapse;margin:0 0 16px;">
    <tr><td style="padding:8px 0;color:#555;">Invoice</td><td style="padding:8px 0;text-align:right;font-weight:600;">${vm.invoiceNumber}</td></tr>
    <tr><td style="padding:8px 0;color:#555;">Amount</td><td style="padding:8px 0;text-align:right;font-weight:600;">${vm.totalFormatted}</td></tr>
    ${dueLine}
  </table>
  ${payButton}
  <hr style="border:none;border-top:1px solid #e5e5e5;margin:32px 0 16px;">
  <p style="margin:0;font-size:13px;color:#888;">${vm.orgName}</p>
</body>
</html>`;

  const text = `Payment Reminder

Hi ${vm.clientName},

This is a friendly reminder that invoice ${vm.invoiceNumber} for ${vm.totalFormatted} is overdue.

${offsetText}Invoice: ${vm.invoiceNumber}
Amount: ${vm.totalFormatted}
${dueText}${payLinkText}
${vm.orgName}`;

  return { subject, html, text };
}
