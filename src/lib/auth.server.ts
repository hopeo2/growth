import { eq, sql } from "drizzle-orm";

import { getDb, type Profile, profiles } from "@/db";

export interface SessionUser {
	id: string;
	email: string;
	displayName: string | null;
	role: "user" | "admin";
	status: "active" | "suspended";
}

export function toSessionUser(profile: Profile): SessionUser {
	return {
		id: profile.id,
		email: profile.email,
		displayName: profile.displayName,
		role: profile.role,
		status: profile.status,
	};
}

function adminEmails(): string[] {
	return (process.env.ADMIN_EMAILS ?? "")
		.split(",")
		.map((entry) => entry.trim().toLowerCase())
		.filter(Boolean);
}

/**
 * Fetch (or lazily create) the profile row that mirrors a Supabase auth user.
 * This also self-heals accounts created before the DB trigger existed and
 * promotes emails listed in `ADMIN_EMAILS`.
 */
export async function ensureProfile(user: {
	id: string;
	email?: string | null;
	user_metadata?: Record<string, unknown> | null;
}): Promise<Profile> {
	const db = getDb();
	const email = (user.email ?? "").toLowerCase();

	let profile = await db.query.profiles.findFirst({
		where: eq(profiles.id, user.id),
	});

	if (!profile) {
		const displayName =
			(user.user_metadata?.display_name as string | undefined) ?? null;
		const shouldBeAdmin = adminEmails().includes(email);
		await db
			.insert(profiles)
			.values({
				id: user.id,
				email,
				displayName,
				role: shouldBeAdmin ? "admin" : "user",
			})
			.onConflictDoNothing();
		profile = await db.query.profiles.findFirst({
			where: eq(profiles.id, user.id),
		});
	}

	if (!profile) {
		throw new Error("Could not load or create the user profile");
	}

	if (profile.email !== email && email) {
		await db
			.update(profiles)
			.set({ email, updatedAt: new Date() })
			.where(eq(profiles.id, user.id));
		profile = { ...profile, email };
	}

	if (profile.role !== "admin" && adminEmails().includes(profile.email)) {
		await db
			.update(profiles)
			.set({ role: "admin", updatedAt: new Date() })
			.where(eq(profiles.id, user.id));
		profile = { ...profile, role: "admin" };
	}

	// Throttled presence update (at most once every 5 minutes).
	await db
		.update(profiles)
		.set({ lastSeenAt: new Date() })
		.where(
			sql`${profiles.id} = ${user.id} and (${profiles.lastSeenAt} is null or ${profiles.lastSeenAt} < now() - interval '5 minutes')`,
		);

	return profile;
}
