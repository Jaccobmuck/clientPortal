export class ResendConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ResendConfigurationError";
  }
}

export type ResendConfig = {
  apiKey: string;
  fromEmail: string;
  testRecipientOverride: string | undefined;
};

export type ResendEmailPayload = {
  from: string;
  to: string[];
  subject: string;
  html: string;
  text: string;
};

export type ResendSendResult =
  | { ok: true; messageId: string }
  | { ok: false; statusCode: number; error: string; retryable: boolean };

export function loadResendConfig(
  env: NodeJS.ProcessEnv = process.env,
): ResendConfig {
  const apiKey = env.RESEND_API_KEY?.trim();
  if (!apiKey) {
    throw new ResendConfigurationError(
      "RESEND_API_KEY is required for the email worker.",
    );
  }

  const fromEmail = env.RESEND_FROM_EMAIL?.trim();
  if (!fromEmail) {
    throw new ResendConfigurationError(
      "RESEND_FROM_EMAIL is required for the email worker.",
    );
  }

  return {
    apiKey,
    fromEmail,
    testRecipientOverride: env.RESEND_TEST_RECIPIENT_OVERRIDE?.trim() || undefined,
  };
}

export async function sendEmail(
  config: ResendConfig,
  payload: ResendEmailPayload,
): Promise<ResendSendResult> {
  let response: Response;

  try {
    response = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: payload.from,
        to: payload.to,
        subject: payload.subject,
        html: payload.html,
        text: payload.text,
      }),
    });
  } catch {
    return { ok: false, statusCode: 0, error: "Network request failed", retryable: true };
  }

  if (response.ok) {
    const body = (await response.json()) as { id?: string };
    return { ok: true, messageId: body.id ?? "unknown" };
  }

  const errorText = await response.text().catch(() => "Unable to read error response");
  const retryable = response.status === 429 || response.status >= 500;

  return {
    ok: false,
    statusCode: response.status,
    error: safeResendErrorMessage(errorText),
    retryable,
  };
}

function safeResendErrorMessage(raw: string): string {
  return raw.length > 500 ? raw.slice(0, 500) + "..." : raw;
}
