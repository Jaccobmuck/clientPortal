const SCHEMA_VERSION = 1;

export function invoicePdfJobId(invoiceId: string): string {
  return `invoice:${requiredId("invoiceId", invoiceId)}:pdf:v${SCHEMA_VERSION}`;
}

export function invoiceInitialEmailJobId(invoiceId: string): string {
  return `invoice:${requiredId("invoiceId", invoiceId)}:initial-email:v${SCHEMA_VERSION}`;
}

export function invoiceReminderScheduleJobId(invoiceId: string): string {
  return `invoice:${requiredId("invoiceId", invoiceId)}:reminder-schedule:v${SCHEMA_VERSION}`;
}

export function invoiceReminderJobId(invoiceId: string, offsetDays: number): string {
  if (!Number.isInteger(offsetDays)) {
    throw new Error("offsetDays must be an integer.");
  }

  return `invoice:${requiredId("invoiceId", invoiceId)}:reminder:${offsetDays}:v${SCHEMA_VERSION}`;
}

export function stripeWebhookJobId(eventId: string): string {
  return `stripe:event:${requiredId("eventId", eventId)}:v${SCHEMA_VERSION}`;
}

function requiredId(name: string, value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${name} is required.`);
  }

  return trimmed;
}
