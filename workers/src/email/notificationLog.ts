import { randomUUID } from "node:crypto";

import type { SupabaseClient } from "@supabase/supabase-js";

import type { EmailType } from "./safety.js";

export type NotificationLogEntry = {
  orgId: string;
  invoiceId: string;
  emailType: EmailType;
  recipientEmail: string;
  resendMessageId: string;
  jobId: string;
  reminderOffsetDays?: number;
};

export function buildNotificationTypeKey(
  emailType: EmailType,
  reminderOffsetDays?: number,
): string {
  if (emailType === "overdue_reminder" && reminderOffsetDays != null) {
    return `email:${emailType}:${reminderOffsetDays}`;
  }
  return `email:${emailType}`;
}

export async function hasAlreadySent(
  supabase: SupabaseClient,
  params: {
    orgId: string;
    invoiceId: string;
    emailType: EmailType;
    reminderOffsetDays?: number;
  },
): Promise<boolean> {
  const typeKey = buildNotificationTypeKey(
    params.emailType,
    params.reminderOffsetDays,
  );

  const { data, error } = await supabase
    .from("notification_log")
    .select("id")
    .eq("org_id", params.orgId)
    .eq("invoice_id", params.invoiceId)
    .eq("type", typeKey)
    .limit(1);

  if (error) {
    throw new Error(
      `Failed to check notification_log: ${error.message}`,
    );
  }

  return (data?.length ?? 0) > 0;
}

export async function recordEmailSent(
  supabase: SupabaseClient,
  entry: NotificationLogEntry,
): Promise<void> {
  const typeKey = buildNotificationTypeKey(
    entry.emailType,
    entry.reminderOffsetDays,
  );

  const { error } = await supabase.from("notification_log").insert({
    id: randomUUID(),
    org_id: entry.orgId,
    invoice_id: entry.invoiceId,
    type: typeKey,
    payload: {
      recipient_email: entry.recipientEmail,
      resend_message_id: entry.resendMessageId,
      job_id: entry.jobId,
    },
  });

  if (error) {
    console.error("Failed to write notification_log", {
      invoiceId: entry.invoiceId,
      emailType: entry.emailType,
      error: error.message,
    });
  }
}
