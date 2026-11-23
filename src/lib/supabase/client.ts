import { createBrowserClient } from "@supabase/ssr";

/**
 * Browser Supabase client. Sessions are stored in cookies by `@supabase/ssr`
 * so the server (via `src/lib/supabase/server.ts`) can read the same session.
 */
let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function createSupabaseBrowserClient() {
	if (browserClient) return browserClient;

	const url = import.meta.env.VITE_SUPABASE_URL;
	const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

	if (!url || !anonKey) {
		throw new Error(
			"VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY must be set at build time.",
		);
	}

	browserClient = createBrowserClient(url, anonKey);
	return browserClient;
}
