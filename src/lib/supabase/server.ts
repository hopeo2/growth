import { createServerClient } from "@supabase/ssr";
import {
	deleteCookie,
	getCookies,
	setCookie,
} from "@tanstack/react-start/server";

import { serverEnv } from "../env.server";

/**
 * Request-scoped Supabase client that reads/writes the auth session cookie.
 * Always call this inside a handler or middleware `.server()` callback — never
 * at module scope.
 */
export function createSupabaseServerClient() {
	return createServerClient(serverEnv.supabaseUrl, serverEnv.supabaseAnonKey, {
		cookies: {
			getAll() {
				return Object.entries(getCookies()).map(([name, value]) => ({
					name,
					value,
				}));
			},
			setAll(cookiesToSet) {
				for (const { name, value, options } of cookiesToSet) {
					if (!value) {
						deleteCookie(name, options);
					} else {
						setCookie(name, value, options);
					}
				}
			},
		},
	});
}
