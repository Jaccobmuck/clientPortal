export type ReminderInvoice = {
  id: string;
  orgId: string;
  status: string;
  dueDate: string | null;
};

export type ReminderConfig = {
  orgId: string;
  timezone?: string | null;
  ruleSource?: unknown;
};

export type ReminderDataSource = {
  loadInvoice(params: { invoiceId: string; orgId: string }): Promise<ReminderInvoice | null>;
  loadReminderConfig(params: { orgId: string }): Promise<ReminderConfig | null>;
};

type FetchLike = typeof fetch;

export function createSupabaseReminderDataSource(
  env: NodeJS.ProcessEnv = process.env,
  fetcher: FetchLike = fetch,
): ReminderDataSource {
  const restUrl = `${requiredEnv(env, "SUPABASE_URL").replace(/\/$/, "")}/rest/v1`;
  const serviceRoleKey = requiredEnv(env, "SUPABASE_SERVICE_ROLE_KEY");

  async function getRows<T>(path: string): Promise<T[]> {
    const response = await fetcher(`${restUrl}/${path}`, {
      headers: {
        apikey: serviceRoleKey,
        authorization: `Bearer ${serviceRoleKey}`,
        accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Supabase reminder query failed with status ${response.status}.`);
    }

    return (await response.json()) as T[];
  }

  return {
    async loadInvoice(params) {
      const rows = await getRows<{
        id: string;
        org_id: string;
        status: string;
        due_date: string | null;
      }>(
        [
          "invoices?select=id,org_id,status,due_date",
          `id=eq.${encodeURIComponent(params.invoiceId)}`,
          `org_id=eq.${encodeURIComponent(params.orgId)}`,
          "limit=1",
        ].join("&"),
      );
      const row = rows[0];

      return row
        ? {
            id: row.id,
            orgId: row.org_id,
            status: row.status,
            dueDate: row.due_date,
          }
        : null;
    },

    async loadReminderConfig(params) {
      const rows = await getRows<{ id: string }>(
        [
          "organizations?select=id",
          `id=eq.${encodeURIComponent(params.orgId)}`,
          "limit=1",
        ].join("&"),
      );

      return rows[0] ? { orgId: rows[0].id } : null;
    },
  };
}

function requiredEnv(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is required for reminder workers.`);
  }

  return value;
}
