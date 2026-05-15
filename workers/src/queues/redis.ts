import { Redis, type RedisOptions } from "ioredis";

export class RedisConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RedisConfigurationError";
  }
}

export type RedisConnectionConfig = {
  url: string;
  options: RedisOptions;
};

const DEFAULT_REDIS_OPTIONS: RedisOptions = {
  maxRetriesPerRequest: null,
};

let sharedRedisConnection: Redis | undefined;

export function assertRedisConfigured(env: NodeJS.ProcessEnv = process.env): string {
  const redisUrl = env.REDIS_URL?.trim();
  if (!redisUrl) {
    throw new RedisConfigurationError("REDIS_URL is required for BullMQ workers.");
  }

  return redisUrl;
}

export function getRedisConnectionOptions(
  env: NodeJS.ProcessEnv = process.env,
): RedisConnectionConfig {
  return {
    url: assertRedisConfigured(env),
    options: { ...DEFAULT_REDIS_OPTIONS },
  };
}

export function createRedisConnection(env: NodeJS.ProcessEnv = process.env): Redis {
  const { url, options } = getRedisConnectionOptions(env);
  return new Redis(url, options);
}

export function getSharedRedisConnection(env: NodeJS.ProcessEnv = process.env): Redis {
  if (!sharedRedisConnection) {
    sharedRedisConnection = createRedisConnection(env);
  }

  return sharedRedisConnection;
}

export async function closeSharedRedisConnection(): Promise<void> {
  if (!sharedRedisConnection) {
    return;
  }

  const connection = sharedRedisConnection;
  sharedRedisConnection = undefined;
  await connection.quit();
}

export type QueueHealthCheckResult =
  | {
      status: "ok";
      latencyMs: number;
    }
  | {
      status: "config_error" | "failed";
      error: string;
    };

export async function queueHealthCheck(
  env: NodeJS.ProcessEnv = process.env,
): Promise<QueueHealthCheckResult> {
  let connection: Redis | undefined;

  try {
    const startedAt = Date.now();
    connection = createRedisConnection(env);
    await connection.ping();
    return {
      status: "ok",
      latencyMs: Date.now() - startedAt,
    };
  } catch (error) {
    if (error instanceof RedisConfigurationError) {
      return {
        status: "config_error",
        error: error.message,
      };
    }

    return {
      status: "failed",
      error: safeRedisErrorMessage(error),
    };
  } finally {
    connection?.disconnect();
  }
}

function safeRedisErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message.replace(/rediss?:\/\/[^\s]+/gi, "redis://***");
  }

  return "Redis health check failed.";
}
