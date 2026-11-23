import { createBrowserClient } from "@supabase/ssr";

/**
 * Browser Supabase client. Sessions are stored in cookies by `@supabase/ssr`
 * so the server (via `src/lib/supabase/server.ts`) can read the same session.
 */
let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function createSupabaseBrowserClient() {
	if (browserClient) return browserClient;

	const url = import.meta.env.VITE_SUPABASE_URL;
	// Supabase's new key format calls the browser-safe key "publishable"; older
	// projects call it the "anon" key. Accept either name.
	const anonKey =
		import.meta.env.VITE_SUPABASE_ANON_KEY ||
		import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

	if (!url || !anonKey) {
		throw new Error(
			"Set VITE_SUPABASE_URL and either VITE_SUPABASE_ANON_KEY (legacy) or VITE_SUPABASE_PUBLISHABLE_KEY (new) at build time.",
		);
	}

	browserClient = createBrowserClient(url, anonKey);
	return browserClient;
}
