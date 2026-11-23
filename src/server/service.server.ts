import { eq } from "drizzle-orm";

import { getDb, type ServiceSettings, serviceSettings } from "@/db";

export const GLOBAL_SETTINGS_ID = "global";

/** Load the singleton service settings row, creating it on first access. */
export async function getServiceSettings(): Promise<ServiceSettings> {
	const db = getDb();
	const rows = await db
		.select()
		.from(serviceSettings)
		.where(eq(serviceSettings.id, GLOBAL_SETTINGS_ID))
		.limit(1);
	if (rows[0]) return rows[0];

	const inserted = await db
		.insert(serviceSettings)
		.values({ id: GLOBAL_SETTINGS_ID })
		.onConflictDoNothing()
		.returning();
	if (inserted[0]) return inserted[0];

	const retry = await db
		.select()
		.from(serviceSettings)
		.where(eq(serviceSettings.id, GLOBAL_SETTINGS_ID))
		.limit(1);
	if (!retry[0]) throw new Error("Could not initialize service settings");
	return retry[0];
}

export async function updateServiceSettings(
	patch: Partial<Omit<ServiceSettings, "id" | "updatedAt">>,
): Promise<ServiceSettings> {
	await getServiceSettings();
	const db = getDb();
	const rows = await db
		.update(serviceSettings)
		.set({ ...patch, updatedAt: new Date() })
		.where(eq(serviceSettings.id, GLOBAL_SETTINGS_ID))
		.returning();
	return rows[0];
}
