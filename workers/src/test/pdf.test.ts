import assert from "node:assert/strict";
import { test } from "node:test";

import { assertPdfRendererUrl } from "../processors/pdfWorker.js";

// ── PDF renderer URL config ──────────────────────────────────

test("assertPdfRendererUrl reads PDF_RENDERER_URL from env", () => {
  const url = assertPdfRendererUrl({
    PDF_RENDERER_URL: "http://api:8000",
  } as unknown as NodeJS.ProcessEnv);

  assert.equal(url, "http://api:8000");
});

test("assertPdfRendererUrl trims whitespace", () => {
  const url = assertPdfRendererUrl({
    PDF_RENDERER_URL: "  http://api:8000  ",
  } as unknown as NodeJS.ProcessEnv);

  assert.equal(url, "http://api:8000");
});

test("assertPdfRendererUrl throws when missing", () => {
  assert.throws(
    () => assertPdfRendererUrl({} as unknown as NodeJS.ProcessEnv),
    /PDF_RENDERER_URL/,
  );
});

test("assertPdfRendererUrl throws when empty", () => {
  assert.throws(
    () =>
      assertPdfRendererUrl({
        PDF_RENDERER_URL: "   ",
      } as unknown as NodeJS.ProcessEnv),
    /PDF_RENDERER_URL/,
  );
});
