import { notFound } from "next/navigation";

import { SmokePage } from "@/components/SmokePage";

export const dynamic = "force-dynamic";

function isSmokeEnabled() {
  return ["1", "true", "yes", "on"].includes(
    String(process.env.ENABLE_SMOKE_TESTS ?? "").toLowerCase(),
  );
}

export default function SmokeRoute() {
  if (!isSmokeEnabled()) {
    notFound();
  }

  return <SmokePage />;
}
