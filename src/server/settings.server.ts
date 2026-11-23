import { eq } from "drizzle-orm";
import type { z } from "zod";

import { type GrowthSettings, getDb, growthSettings } from "@/db";
import type { growthSettingsSchema } from "@/lib/schemas";
import { requireOwnedAccount } from "./access.server";

type GrowthSettingsInput = z.infer<typeof growthSettingsSchema>;

/** Load growth settings for an account, creating the row if missing. */
export async function ensureGrowthSettings(
	accountId: string,
): Promise<GrowthSettings> {
	const db = getDb();
	const rows = await db
		.select()
		.from(growthSettings)
		.where(eq(growthSettings.accountId, accountId))
		.limit(1);
	if (rows[0]) return rows[0];

	const inserted = await db
		.insert(growthSettings)
		.values({ accountId })
		.onConflictDoNothing()
		.returning();
	if (inserted[0]) return inserted[0];

	const retry = await db
		.select()
		.from(growthSettings)
		.where(eq(growthSettings.accountId, accountId))
		.limit(1);
	if (!retry[0]) throw new Error("Could not load growth settings");
	return retry[0];
}

export async function getGrowthSettings(
	userId: string,
	accountId: string,
): Promise<GrowthSettings> {
	await requireOwnedAccount(userId, accountId);
	return ensureGrowthSettings(accountId);
}

export async function saveGrowthSettings(
	userId: string,
	input: GrowthSettingsInput,
): Promise<GrowthSettings> {
	await requireOwnedAccount(userId, input.accountId);
	await ensureGrowthSettings(input.accountId);

	const db = getDb();
	const { accountId, ...values } = input;
	const rows = await db
		.update(growthSettings)
		.set({ ...values, updatedAt: new Date() })
		.where(eq(growthSettings.accountId, accountId))
		.returning();
	return rows[0];
}
