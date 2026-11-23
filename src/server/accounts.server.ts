import { and, desc, eq, inArray } from "drizzle-orm";

import { getDb, growthSettings, instagramAccounts } from "@/db";
import { encryptSecret } from "@/lib/crypto.server";
import { enqueueJob } from "./jobs.server";
import { getServiceSettings } from "./service.server";

/** Columns that are safe to send to the browser (never `credentials`). */
const publicColumns = {
	id: instagramAccounts.id,
	username: instagramAccounts.username,
	proxyUrl: instagramAccounts.proxyUrl,
	status: instagramAccounts.status,
	followers: instagramAccounts.followers,
	following: instagramAccounts.following,
	posts: instagramAccounts.posts,
	lastLoginAt: instagramAccounts.lastLoginAt,
	lastRunAt: instagramAccounts.lastRunAt,
	lastError: instagramAccounts.lastError,
	createdAt: instagramAccounts.createdAt,
	updatedAt: instagramAccounts.updatedAt,
};

export interface AccountSummary {
	id: string;
	username: string;
	proxyUrl: string | null;
	status: "pending" | "active" | "paused" | "error" | "verification_required";
	followers: number;
	following: number;
	posts: number;
	lastLoginAt: Date | null;
	lastRunAt: Date | null;
	lastError: string | null;
	createdAt: Date;
	updatedAt: Date;
	growthEnabled: boolean;
}

export async function listAccounts(userId: string): Promise<AccountSummary[]> {
	const db = getDb();
	const accounts = await db
		.select(publicColumns)
		.from(instagramAccounts)
		.where(eq(instagramAccounts.userId, userId))
		.orderBy(desc(instagramAccounts.createdAt));

	if (accounts.length === 0) return [];

	const settingsRows = await db
		.select({
			accountId: growthSettings.accountId,
			enabled: growthSettings.enabled,
		})
		.from(growthSettings)
		.where(
			inArray(
				growthSettings.accountId,
				accounts.map((account) => account.id),
			),
		);
	const enabledMap = new Map(
		settingsRows.map((row) => [row.accountId, row.enabled]),
	);

	return accounts.map((account) => ({
		...account,
		growthEnabled: enabledMap.get(account.id) ?? false,
	}));
}

export async function getAccountSummary(
	userId: string,
	accountId: string,
): Promise<AccountSummary | null> {
	const accounts = await listAccounts(userId);
	return accounts.find((account) => account.id === accountId) ?? null;
}

export async function createAccount(
	userId: string,
	input: { username: string; password: string; proxyUrl: string | null },
): Promise<{ id: string }> {
	const db = getDb();
	const service = await getServiceSettings();

	const existing = await db
		.select({ id: instagramAccounts.id })
		.from(instagramAccounts)
		.where(eq(instagramAccounts.userId, userId));

	if (
		service.maxAccountsPerUser > 0 &&
		existing.length >= service.maxAccountsPerUser
	) {
		throw new Error(
			`Account limit reached (${service.maxAccountsPerUser} per user)`,
		);
	}

	const inserted = await db
		.insert(instagramAccounts)
		.values({
			userId,
			username: input.username,
			credentials: encryptSecret(input.password),
			proxyUrl: input.proxyUrl,
			status: "pending",
		})
		.returning({ id: instagramAccounts.id });

	const account = inserted[0];
	if (!account) throw new Error("Could not create the account");

	await db.insert(growthSettings).values({
		accountId: account.id,
		likesPerDay: service.defaultLikesPerDay,
		followsPerDay: service.defaultFollowsPerDay,
		unfollowsPerDay: service.defaultUnfollowsPerDay,
		commentsPerDay: service.defaultCommentsPerDay,
	});

	// Ask the worker to verify the credentials straight away.
	await enqueueJob(userId, account.id, "login_check");

	return { id: account.id };
}

export async function updateAccount(
	userId: string,
	input: {
		accountId: string;
		proxyUrl: string | null;
		status?: "active" | "paused";
	},
): Promise<void> {
	const db = getDb();
	await db
		.update(instagramAccounts)
		.set({
			proxyUrl: input.proxyUrl,
			...(input.status ? { status: input.status } : {}),
			updatedAt: new Date(),
		})
		.where(
			and(
				eq(instagramAccounts.id, input.accountId),
				eq(instagramAccounts.userId, userId),
			),
		);
}

export async function updateAccountPassword(
	userId: string,
	input: { accountId: string; password: string },
): Promise<void> {
	const db = getDb();
	await db
		.update(instagramAccounts)
		.set({
			credentials: encryptSecret(input.password),
			status: "pending",
			lastError: null,
			updatedAt: new Date(),
		})
		.where(
			and(
				eq(instagramAccounts.id, input.accountId),
				eq(instagramAccounts.userId, userId),
			),
		);
}

export async function deleteAccount(
	userId: string,
	accountId: string,
): Promise<void> {
	const db = getDb();
	await db
		.delete(instagramAccounts)
		.where(
			and(
				eq(instagramAccounts.id, accountId),
				eq(instagramAccounts.userId, userId),
			),
		);
}
