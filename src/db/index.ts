import { drizzle, type PostgresJsDatabase } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import * as schema from "./schema";

let cached: PostgresJsDatabase<typeof schema> | null = null;
let cachedClient: ReturnType<typeof postgres> | null = null;

/**
 * Lazily create the Postgres connection so env vars are read per-process
 * lifetime rather than at module import (which also runs during builds).
 *
 * `prepare: false` is required for Supabase's transaction pooler
 * (Supavisor, port 6543).
 */
export function getDb(): PostgresJsDatabase<typeof schema> {
	if (cached) return cached;

	const url = process.env.DATABASE_URL;
	if (!url) {
		throw new Error("DATABASE_URL is not set. See .env.example and README.md.");
	}

	cachedClient = postgres(url, {
		prepare: false,
		max: Number(process.env.DATABASE_POOL_MAX ?? 5),
		idle_timeout: 20,
		connect_timeout: 15,
	});
	cached = drizzle(cachedClient, { schema });
	return cached;
}

export async function closeDb(): Promise<void> {
	if (cachedClient) {
		await cachedClient.end({ timeout: 5 });
		cachedClient = null;
		cached = null;
	}
}

export { schema };
export * from "./schema";

export type Database = PostgresJsDatabase<typeof schema>;
export type Transaction = Parameters<Parameters<Database["transaction"]>[0]>[0];
