import { Worker, UnrecoverableError, type Job } from "bullmq";

import { QUEUE_NAMES } from "../queues/constants.js";
import type { PdfQueueJob } from "../queues/factory.js";
import { getSharedRedisConnection } from "../queues/redis.js";
import type { InvoicePdfJob, SmokeQueueJob } from "../types/jobs.js";

type PdfRenderResponse = {
  success: boolean;
  storage_path: string | null;
  file_size: number | null;
  error: string | null;
  permanent: boolean;
};

export function assertPdfRendererUrl(env: NodeJS.ProcessEnv = process.env): string {
  const url = env.PDF_RENDERER_URL?.trim();
  if (!url) {
    throw new UnrecoverableError(
      "PDF_RENDERER_URL is required for the PDF worker.",
    );
  }
  return url;
}

function isSmokeJob(data: PdfQueueJob): data is SmokeQueueJob {
  return "smoke" in data && (data as SmokeQueueJob).smoke === true;
}

function isPdfJob(data: PdfQueueJob): data is InvoicePdfJob {
  return "invoiceId" in data && !isSmokeJob(data);
}

async function processPdfJob(job: Job<PdfQueueJob>): Promise<void> {
  if (isSmokeJob(job.data)) {
    console.log(`[${QUEUE_NAMES.PDF}] smoke job completed`, {
      jobId: job.id,
      correlationId: job.data.correlationId,
    });
    return;
  }

  if (!isPdfJob(job.data)) {
    throw new UnrecoverableError("Invalid job payload: not a PDF or smoke job");
  }

  const data = job.data;

  if (data.schemaVersion !== 1) {
    throw new UnrecoverableError(
      `Unsupported schemaVersion: ${data.schemaVersion}`,
    );
  }

  if (!data.invoiceId || !data.orgId) {
    throw new UnrecoverableError(
      "Missing required fields: invoiceId, orgId",
    );
  }

  const rendererUrl = assertPdfRendererUrl();

  let response: Response;
  try {
    response = await fetch(`${rendererUrl}/internal/pdf/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        invoice_id: data.invoiceId,
        org_id: data.orgId,
      }),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    throw new Error(`PDF renderer unreachable: ${message}`);
  }

  let body: PdfRenderResponse;
  try {
    body = (await response.json()) as PdfRenderResponse;
  } catch {
    throw new Error(
      `PDF renderer returned invalid JSON (HTTP ${response.status})`,
    );
  }

  if (!body.success) {
    const errorMessage = body.error ?? "Unknown PDF render error";
    if (body.permanent) {
      throw new UnrecoverableError(errorMessage);
    }
    throw new Error(errorMessage);
  }

  console.log(`[${QUEUE_NAMES.PDF}] PDF rendered and uploaded`, {
    jobId: job.id,
    invoiceId: data.invoiceId,
    storagePath: body.storage_path,
    fileSize: body.file_size,
  });
}

export function createPdfWorker(): Worker<PdfQueueJob> {
  return new Worker<PdfQueueJob>(
    QUEUE_NAMES.PDF,
    processPdfJob,
    { connection: getSharedRedisConnection() },
  );
}
