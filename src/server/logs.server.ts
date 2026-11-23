import { and, desc, eq, gte, inArray } from "drizzle-orm";

import {
	type ActivityLog,
	accountStatsDaily,
	activityLogs,
	getDb,
	type JsonObject,
} from "@/db";

export type ActivityAction =
	| "like"
	| "follow"
	| "unfollow"
	| "comment"
	| "story"
	| "login"
	| "info"
	| "warning"
	| "error";

export interface ActivityLogInput {
	userId: string;
	accountId: string;
	jobId?: string | null;
	action: ActivityAction;
	target?: string | null;
	message?: string | null;
	detail?: JsonObject | null;
}

export async function logActivity(input: ActivityLogInput): Promise<void> {
	const db = getDb();
	await db.insert(activityLogs).values({
		userId: input.userId,
		accountId: input.accountId,
		jobId: input.jobId ?? null,
		action: input.action,
		target: input.target ?? null,
		message: input.message ?? null,
		detail: input.detail ?? null,
	});
}

/** Bulk insert events reported by the Python worker for a single job. */
export async function ingestActivityBatch(
	userId: string,
	accountId: string,
	jobId: string,
	events: Array<{
		action: ActivityAction;
		target?: string | null;
		message?: string | null;
		detail?: JsonObject | null;
	}>,
): Promise<number> {
	if (events.length === 0) return 0;
	const db = getDb();
	const rows = events.slice(0, 500).map((event) => ({
		userId,
		accountId,
		jobId,
		action: event.action,
		target: event.target ?? null,
		message: event.message?.slice(0, 500) ?? null,
		detail: event.detail ?? null,
	}));
	await db.insert(activityLogs).values(rows);
	return rows.length;
}

export async function listActivityLogs(
	userId: string,
	options: {
		accountId?: string;
		actions?: ActivityAction[];
		limit?: number;
	} = {},
): Promise<ActivityLog[]> {
	const db = getDb();
	const filters = [eq(activityLogs.userId, userId)];
	if (options.accountId) {
		filters.push(eq(activityLogs.accountId, options.accountId));
	}
	if (options.actions && options.actions.length > 0) {
		filters.push(inArray(activityLogs.action, options.actions));
	}
	return db
		.select()
		.from(activityLogs)
		.where(and(...filters))
		.orderBy(desc(activityLogs.createdAt))
		.limit(Math.min(options.limit ?? 100, 500));
}

export interface DailyStatRow {
	day: string;
	likes: number;
	follows: number;
	unfollows: number;
	comments: number;
	stories: number;
	errors: number;
	followers: number | null;
	following: number | null;
	posts: number | null;
}

export async function listDailyStats(
	userId: string,
	options: { accountId?: string; days?: number } = {},
): Promise<Array<DailyStatRow & { accountId: string }>> {
	const db = getDb();
	const days = Math.min(options.days ?? 30, 365);
	const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000)
		.toISOString()
		.slice(0, 10);

	const filters = [
		eq(accountStatsDaily.userId, userId),
		gte(accountStatsDaily.day, since),
	];
	if (options.accountId) {
		filters.push(eq(accountStatsDaily.accountId, options.accountId));
	}

	const rows = await db
		.select()
		.from(accountStatsDaily)
		.where(and(...filters))
		.orderBy(accountStatsDaily.day);

	return rows.map((row) => ({
		accountId: row.accountId,
		day: row.day,
		likes: row.likes,
		follows: row.follows,
		unfollows: row.unfollows,
		comments: row.comments,
		stories: row.stories,
		errors: row.errors,
		followers: row.followers,
		following: row.following,
		posts: row.posts,
	}));
}
