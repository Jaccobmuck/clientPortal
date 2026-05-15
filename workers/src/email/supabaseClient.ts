import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export class SupabaseConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SupabaseConfigurationError";
  }
}

export type SupabaseWorkerConfig = {
  url: string;
  serviceRoleKey: string;
};

export function assertSupabaseConfigured(
  env: NodeJS.ProcessEnv = process.env,
): SupabaseWorkerConfig {
  const url = env.SUPABASE_URL?.trim();
  if (!url) {
    throw new SupabaseConfigurationError(
      "SUPABASE_URL is required for the email worker.",
    );
  }

  const serviceRoleKey = env.SUPABASE_SERVICE_ROLE_KEY?.trim();
  if (!serviceRoleKey) {
    throw new SupabaseConfigurationError(
      "SUPABASE_SERVICE_ROLE_KEY is required for the email worker.",
    );
  }

  return { url, serviceRoleKey };
}

export function createWorkerSupabaseClient(
  env: NodeJS.ProcessEnv = process.env,
): SupabaseClient {
  const { url, serviceRoleKey } = assertSupabaseConfigured(env);

  return createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

let sharedClient: SupabaseClient | undefined;

export function getWorkerSupabaseClient(
  env: NodeJS.ProcessEnv = process.env,
): SupabaseClient {
  if (!sharedClient) {
    sharedClient = createWorkerSupabaseClient(env);
  }
  return sharedClient;
}
