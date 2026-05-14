"use client";

import { useEffect, useMemo, useState } from "react";

type ApiError = {
  code: string;
  message: string;
};

type ApiResponse<T> = {
  success: boolean;
  data: T | null;
  error?: ApiError | null;
};

type ConfigCheck = {
  name: string;
  present: boolean;
};

type SmokeConfig = {
  enabled: boolean;
  all_required_present: boolean;
  required: ConfigCheck[];
};

type SmokeActionName = "queue" | "email" | "pdf" | "reminder";

type SmokeActionResult = {
  action: SmokeActionName;
  status: "placeholder";
  implemented: boolean;
  message: string;
};

const actionCards: Array<{
  action: SmokeActionName;
  title: string;
  label: string;
}> = [
  { action: "queue", title: "Redis queue test", label: "Run queue check" },
  { action: "email", title: "Email test", label: "Run email check" },
  { action: "pdf", title: "PDF render/upload test", label: "Run PDF check" },
  { action: "reminder", title: "Delayed reminder test", label: "Run reminder check" },
];

function statusText(check?: ConfigCheck) {
  if (!check) {
    return "Unknown";
  }
  return check.present ? "Present" : "Missing";
}

async function readApiResponse<T>(response: Response): Promise<T> {
  const body = (await response.json()) as ApiResponse<T>;
  if (!response.ok || !body.success || !body.data) {
    throw new Error(body.error?.message ?? "Smoke check failed");
  }
  return body.data;
}

export function SmokePage() {
  const [config, setConfig] = useState<SmokeConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);
  const [busyAction, setBusyAction] = useState<SmokeActionName | null>(null);
  const [results, setResults] = useState<Partial<Record<SmokeActionName, SmokeActionResult>>>(
    {},
  );

  useEffect(() => {
    let isMounted = true;

    async function loadConfig() {
      try {
        const response = await fetch("/api/v1/smoke/config", {
          cache: "no-store",
        });
        const data = await readApiResponse<SmokeConfig>(response);
        if (isMounted) {
          setConfig(data);
        }
      } catch (error) {
        if (isMounted) {
          setConfigError(error instanceof Error ? error.message : "Smoke config unavailable");
        }
      } finally {
        if (isMounted) {
          setIsLoadingConfig(false);
        }
      }
    }

    loadConfig();

    return () => {
      isMounted = false;
    };
  }, []);

  const configByName = useMemo(() => {
    return new Map(config?.required.map((check) => [check.name, check]) ?? []);
  }, [config]);

  async function runAction(action: SmokeActionName) {
    setBusyAction(action);
    try {
      const response = await fetch(`/api/v1/smoke/${action}`, {
        method: "POST",
      });
      const data = await readApiResponse<SmokeActionResult>(response);
      setResults((current) => ({ ...current, [action]: data }));
    } catch (error) {
      setResults((current) => ({
        ...current,
        [action]: {
          action,
          status: "placeholder",
          implemented: false,
          message: error instanceof Error ? error.message : "Smoke action unavailable",
        },
      }));
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <main className="smoke-page">
      <section className="smoke-shell">
        <header className="smoke-header">
          <div>
            <p className="eyebrow">Dev smoke</p>
            <h1>Freelio smoke checks</h1>
          </div>
          <span className="smoke-state">{config?.enabled ? "Enabled" : "Checking"}</span>
        </header>

        <section className="smoke-grid">
          <article className="card smoke-card smoke-card--wide">
            <div className="smoke-card__header">
              <div>
                <span className="smoke-card__icon">CFG</span>
                <h2>Config status</h2>
              </div>
              <span
                className={
                  config?.all_required_present
                    ? "smoke-pill smoke-pill--ok"
                    : "smoke-pill smoke-pill--warn"
                }
              >
                {isLoadingConfig
                  ? "Loading"
                  : config?.all_required_present
                    ? "Ready"
                    : "Needs env"}
              </span>
            </div>

            {configError ? <p className="smoke-error">{configError}</p> : null}

            <dl className="smoke-config-list">
              {(config?.required ?? []).map((check) => (
                <div key={check.name}>
                  <dt>{check.name}</dt>
                  <dd className={check.present ? "smoke-ok" : "smoke-warn"}>
                    {statusText(check)}
                  </dd>
                </div>
              ))}
              {!config && !configError
                ? ["SECRET_KEY", "DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].map(
                    (name) => (
                      <div key={name}>
                        <dt>{name}</dt>
                        <dd>Checking</dd>
                      </div>
                    ),
                  )
                : null}
            </dl>
          </article>

          {actionCards.map((card) => {
            const result = results[card.action];
            const redisReady = configByName.get("REDIS_URL")?.present;

            return (
              <article className="card smoke-card" key={card.action}>
                <div className="smoke-card__header">
                  <div>
                    <span className="smoke-card__icon">{card.action.slice(0, 3).toUpperCase()}</span>
                    <h2>{card.title}</h2>
                  </div>
                  <span className="smoke-pill">Placeholder</span>
                </div>

                <p className="smoke-card__message">
                  {result?.message ??
                    (card.action === "queue" && redisReady === false
                      ? "Redis config is not present."
                      : "Ready to call the smoke endpoint.")}
                </p>

                <button
                  className="primary-button smoke-action"
                  disabled={busyAction !== null}
                  onClick={() => runAction(card.action)}
                  type="button"
                >
                  {busyAction === card.action ? "Running" : card.label}
                </button>
              </article>
            );
          })}
        </section>
      </section>
    </main>
  );
}
