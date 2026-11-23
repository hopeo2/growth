import { createMiddleware } from "@tanstack/react-start";

import { ensureProfile } from "./auth.server";
import { createSupabaseServerClient } from "./supabase/server";

/**
 * Server-function middlewares live in this module (not in a `*.server.*` file)
 * because client-reachable `.functions.ts` files need to reference the
 * middleware objects. Their server-only dependencies are imported at the top
 * but only used inside the `.server()` callbacks, so the Start compiler strips
 * them from the client build.
 */

/** Require an authenticated, non-suspended user. */
export const authMiddleware = createMiddleware({ type: "function" }).server(
	async ({ next }) => {
		const supabase = createSupabaseServerClient();
		const {
			data: { user },
			error,
		} = await supabase.auth.getUser();

		if (error || !user) {
			throw new Error("Unauthorized");
		}

		const profile = await ensureProfile(user);
		if (profile.status === "suspended") {
			throw new Error("This account has been suspended");
		}

		return next({ context: { user, profile } });
	},
);

/** Require an authenticated admin. */
export const adminMiddleware = createMiddleware({ type: "function" })
	.middleware([authMiddleware])
	.server(async ({ next, context }) => {
		if (context.profile.role !== "admin") {
			throw new Error("Forbidden: admins only");
		}
		return next();
	});
