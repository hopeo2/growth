import { createServerFn } from "@tanstack/react-start";
import { getServiceSettings } from "@/server/service.server";
import { ensureProfile, toSessionUser } from "./auth.server";
import { createSupabaseServerClient } from "./supabase/server";

/**
 * Returns the current session user (or null) as a plain, serializable object.
 * Used by the root route `beforeLoad` to populate router context.
 */
export const getCurrentUser = createServerFn({ method: "GET" }).handler(
	async () => {
		try {
			const supabase = createSupabaseServerClient();
			const {
				data: { user },
			} = await supabase.auth.getUser();
			if (!user) return null;

			const profile = await ensureProfile(user);
			if (profile.status === "suspended") return null;

			return toSessionUser(profile);
		} catch {
			// Missing config or an expired/invalid session should not crash SSR.
			return null;
		}
	},
);

/** Public, unauthenticated config used by the signup page. */
export const getPublicConfig = createServerFn({ method: "GET" }).handler(
	async () => {
		try {
			const settings = await getServiceSettings();
			return {
				registrationOpen: settings.registrationOpen,
				maintenanceMode: settings.maintenanceMode,
				maxAccountsPerUser: settings.maxAccountsPerUser,
			};
		} catch {
			return {
				registrationOpen: true,
				maintenanceMode: false,
				maxAccountsPerUser: 3,
			};
		}
	},
);
