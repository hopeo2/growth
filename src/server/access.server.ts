import { and, eq } from "drizzle-orm";

import { getDb, type InstagramAccount, instagramAccounts } from "@/db";

/** Load an account only if it belongs to the given user. */
export async function getOwnedAccount(
	userId: string,
	accountId: string,
): Promise<InstagramAccount | null> {
	const db = getDb();
	const rows = await db
		.select()
		.from(instagramAccounts)
		.where(
			and(
				eq(instagramAccounts.id, accountId),
				eq(instagramAccounts.userId, userId),
			),
		)
		.limit(1);
	return rows[0] ?? null;
}

/** Throw when the account does not exist or is not owned by the user. */
export async function requireOwnedAccount(
	userId: string,
	accountId: string,
): Promise<InstagramAccount> {
	const account = await getOwnedAccount(userId, accountId);
	if (!account) {
		throw new Error("Account not found");
	}
	return account;
}
