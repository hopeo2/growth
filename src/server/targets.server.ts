import { and, asc, eq } from "drizzle-orm";

import { getDb, type Target, targets } from "@/db";
import { requireOwnedAccount } from "./access.server";

export async function listTargets(
	userId: string,
	accountId: string,
): Promise<Target[]> {
	await requireOwnedAccount(userId, accountId);
	const db = getDb();
	return db
		.select()
		.from(targets)
		.where(eq(targets.accountId, accountId))
		.orderBy(asc(targets.kind), asc(targets.value));
}

export async function addTarget(
	userId: string,
	input: {
		accountId: string;
		kind: "hashtag" | "username" | "location";
		value: string;
	},
): Promise<Target> {
	await requireOwnedAccount(userId, input.accountId);
	const db = getDb();

	const normalized = input.value.replace(/^#+/, "").trim().toLowerCase();
	if (!normalized) throw new Error("Target value is required");

	const inserted = await db
		.insert(targets)
		.values({
			accountId: input.accountId,
			kind: input.kind,
			value: normalized,
		})
		.onConflictDoNothing()
		.returning();

	if (inserted[0]) return inserted[0];

	const existing = await db
		.select()
		.from(targets)
		.where(
			and(
				eq(targets.accountId, input.accountId),
				eq(targets.kind, input.kind),
				eq(targets.value, normalized),
			),
		)
		.limit(1);
	if (!existing[0]) throw new Error("Could not add the target");
	return existing[0];
}

export async function removeTarget(
	userId: string,
	input: { accountId: string; targetId: string },
): Promise<void> {
	await requireOwnedAccount(userId, input.accountId);
	const db = getDb();
	await db
		.delete(targets)
		.where(
			and(
				eq(targets.id, input.targetId),
				eq(targets.accountId, input.accountId),
			),
		);
}

export async function toggleTarget(
	userId: string,
	input: { accountId: string; targetId: string; enabled: boolean },
): Promise<void> {
	await requireOwnedAccount(userId, input.accountId);
	const db = getDb();
	await db
		.update(targets)
		.set({ enabled: input.enabled })
		.where(
			and(
				eq(targets.id, input.targetId),
				eq(targets.accountId, input.accountId),
			),
		);
}

export interface ResolvedTargets {
	hashtags: string[];
	users: string[];
	locations: string[];
}

/** Active targets grouped by kind, ready to embed in a job payload. */
export async function resolveActiveTargets(
	accountId: string,
): Promise<ResolvedTargets> {
	const db = getDb();
	const rows = await db
		.select({ kind: targets.kind, value: targets.value })
		.from(targets)
		.where(and(eq(targets.accountId, accountId), eq(targets.enabled, true)));

	const resolved: ResolvedTargets = { hashtags: [], users: [], locations: [] };
	for (const row of rows) {
		if (row.kind === "hashtag") resolved.hashtags.push(row.value);
		else if (row.kind === "username") resolved.users.push(row.value);
		else resolved.locations.push(row.value);
	}
	return resolved;
}
