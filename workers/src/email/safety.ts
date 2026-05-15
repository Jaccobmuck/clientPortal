export class EmailSafetyError extends Error {
  readonly permanent: boolean;

  constructor(message: string, permanent: boolean) {
    super(message);
    this.name = "EmailSafetyError";
    this.permanent = permanent;
  }
}

export type EmailType =
  | "invoice_sent"
  | "payment_received"
  | "payment_confirmed"
  | "overdue_reminder";

const ALLOWED_STATUSES: Record<EmailType, readonly string[]> = {
  invoice_sent: ["sent", "locked"],
  payment_received: ["sent", "locked", "paid"],
  payment_confirmed: ["paid"],
  overdue_reminder: ["sent", "locked", "overdue"],
};

export function validateEmailSafety(
  emailType: EmailType,
  invoiceStatus: string,
): void {
  const allowed = ALLOWED_STATUSES[emailType];
  if (!allowed) {
    throw new EmailSafetyError(
      `Unknown email type: ${emailType}`,
      true,
    );
  }

  if (allowed.includes(invoiceStatus)) {
    return;
  }

  throw new EmailSafetyError(
    `Cannot send ${emailType} email for invoice with status "${invoiceStatus}"`,
    true,
  );
}

export function validateRecipient(email: string | null | undefined): void {
  if (!email || !email.trim()) {
    throw new EmailSafetyError("Recipient email is missing", true);
  }

  const trimmed = email.trim();
  const atIndex = trimmed.indexOf("@");
  if (atIndex < 1) {
    throw new EmailSafetyError("Recipient email is invalid", true);
  }

  const domain = trimmed.slice(atIndex + 1);
  if (!domain.includes(".")) {
    throw new EmailSafetyError("Recipient email is invalid", true);
  }
}
