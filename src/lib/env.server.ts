/**
 * Server-side environment access. Read values inside request handlers or
 * server-only modules, never at module scope in isomorphic code.
 */

function requiredAny(names: string[]): string {
	for (const name of names) {
		const value = process.env[name];
		if (value) return value;
	}
	throw new Error(
		`Missing required environment variable (${names.join(" or ")}). Copy .env.example to .env and fill it in.`,
	);
}

function required(name: string): string {
	return requiredAny([name]);
}

function optional(name: string, fallback: string): string {
	return process.env[name] ?? fallback;
}

export const serverEnv = {
	get databaseUrl() {
		return required("DATABASE_URL");
	},
	get supabaseUrl() {
		return requiredAny(["SUPABASE_URL", "VITE_SUPABASE_URL"]);
	},
	get supabaseAnonKey() {
		// "publishable" is the new name for the browser-safe (legacy "anon") key.
		return requiredAny([
			"SUPABASE_ANON_KEY",
			"VITE_SUPABASE_ANON_KEY",
			"SUPABASE_PUBLISHABLE_KEY",
			"VITE_SUPABASE_PUBLISHABLE_KEY",
		]);
	},
	get supabaseServiceRoleKey() {
		// New projects expose this as a "secret" key: sb_secret_...
		return requiredAny(["SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"]);
	},
	get encryptionKey() {
		return required("CREDENTIALS_ENCRYPTION_KEY");
	},
	get appOrigin() {
		return optional("APP_ORIGIN", "http://localhost:3000");
	},
	/** Shared bearer token that the Python worker uses to call the worker API. */
	get workerApiToken() {
		return required("WORKER_API_TOKEN");
	},
};

/** Public (browser-visible) config. */
export function publicEnv() {
	return {
		supabaseUrl: process.env.SUPABASE_URL ?? "",
		supabaseAnonKey: process.env.SUPABASE_ANON_KEY ?? "",
	};
}
