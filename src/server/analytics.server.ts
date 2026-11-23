import { and, count, eq, gte, inArray } from "drizzle-orm";
import type { ActivityLog, Job } from "@/db";
import { activityLogs, getDb } from "@/db";
import { type AccountSummary, listAccounts } from "./accounts.server";
import { listJobsForUser } from "./jobs.server";
import {
	type ActivityAction,
	type DailyStatRow,
	listActivityLogs,
	listDailyStats,
} from "./logs.server";
import { resolveActiveTargets } from "./targets.server";

export interface DaySeries {
	day: string;
	likes: number;
	follows: number;
	unfollows: number;
	comments: number;
	stories: number;
	errors: number;
}

export interface Totals {
	likes: number;
	follows: number;
	unfollows: number;
	comments: number;
	stories: number;
	errors: number;
	interactions: number;
}

function emptyTotals(): Totals {
	return {
		likes: 0,
		follows: 0,
		unfollows: 0,
		comments: 0,
		stories: 0,
		errors: 0,
		interactions: 0,
	};
}

function accumulate(totals: Totals, row: DailyStatRow): Totals {
	totals.likes += row.likes;
	totals.follows += row.follows;
	totals.unfollows += row.unfollows;
	totals.comments += row.comments;
	totals.stories += row.stories;
	totals.errors += row.errors;
	totals.interactions += row.likes + row.follows + row.comments + row.stories;
	return totals;
}

/** Build a zero-filled day series over the last `days` days. */
export function buildSeries(
	rows: Array<DailyStatRow>,
	days: number,
): DaySeries[] {
	const byDay = new Map<string, DaySeries>();
	for (const row of rows) {
		const existing = byDay.get(row.day) ?? {
			day: row.day,
			likes: 0,
			follows: 0,
			unfollows: 0,
			comments: 0,
			stories: 0,
			errors: 0,
		};
		existing.likes += row.likes;
		existing.follows += row.follows;
		existing.unfollows += row.unfollows;
		existing.comments += row.comments;
		existing.stories += row.stories;
		existing.errors += row.errors;
		byDay.set(row.day, existing);
	}

	const series: DaySeries[] = [];
	for (let index = days - 1; index >= 0; index -= 1) {
		const day = new Date(Date.now() - index * 24 * 60 * 60 * 1000)
			.toISOString()
			.slice(0, 10);
		series.push(
			byDay.get(day) ?? {
				day,
				likes: 0,
				follows: 0,
				unfollows: 0,
				comments: 0,
				stories: 0,
				errors: 0,
			},
		);
	}
	return series;
}

export interface DashboardData {
	accounts: AccountSummary[];
	totals: { today: Totals; last7: Totals; last30: Totals };
	series: DaySeries[];
	recentLogs: ActivityLog[];
	activeJobs: Job[];
	followerTotal: number;
	followingTotal: number;
	postTotal: number;
}

export async function getDashboard(userId: string): Promise<DashboardData> {
	const [accounts, daily, recentLogs, jobs] = await Promise.all([
		listAccounts(userId),
		listDailyStats(userId, { days: 30 }),
		listActivityLogs(userId, { limit: 10 }),
		listJobsForUser(userId, 25),
	]);

	const today = new Date().toISOString().slice(0, 10);
	const todayTotals = emptyTotals();
	const last7 = emptyTotals();
	const last30 = emptyTotals();
	const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)
		.toISOString()
		.slice(0, 10);

	for (const row of daily) {
		accumulate(last30, row);
		if (row.day >= sevenDaysAgo) accumulate(last7, row);
		if (row.day === today) accumulate(todayTotals, row);
	}

	return {
		accounts,
		totals: { today: todayTotals, last7, last30 },
		series: buildSeries(daily, 14),
		recentLogs,
		activeJobs: jobs.filter(
			(job) => job.status === "queued" || job.status === "running",
		),
		followerTotal: accounts.reduce(
			(sum, account) => sum + account.followers,
			0,
		),
		followingTotal: accounts.reduce(
			(sum, account) => sum + account.following,
			0,
		),
		postTotal: accounts.reduce((sum, account) => sum + account.posts, 0),
	};
}

export interface ActionBreakdown {
	action: ActivityAction;
	total: number;
}

export async function getActionBreakdown(
	userId: string,
	options: { accountId?: string; days?: number } = {},
): Promise<ActionBreakdown[]> {
	const db = getDb();
	const days = Math.min(options.days ?? 30, 365);
	const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

	const filters = [
		eq(activityLogs.userId, userId),
		gte(activityLogs.createdAt, since),
		inArray(activityLogs.action, [
			"like",
			"follow",
			"unfollow",
			"comment",
			"story",
			"error",
		]),
	];
	if (options.accountId)
		filters.push(eq(activityLogs.accountId, options.accountId));

	const rows = await db
		.select({ action: activityLogs.action, total: count() })
		.from(activityLogs)
		.where(and(...filters))
		.groupBy(activityLogs.action);

	return rows.map((row) => ({ action: row.action, total: Number(row.total) }));
}

export interface AnalyticsData {
	series: DaySeries[];
	totals: Totals;
	accounts: AccountSummary[];
	breakdown: ActionBreakdown[];
	accountId: string | null;
	targetCounts: { hashtags: number; users: number; locations: number } | null;
}

export async function getAnalytics(
	userId: string,
	options: { accountId?: string; days?: number } = {},
): Promise<AnalyticsData> {
	const days = Math.min(options.days ?? 30, 365);
	const [daily, accounts, breakdown] = await Promise.all([
		listDailyStats(userId, { accountId: options.accountId, days }),
		listAccounts(userId),
		getActionBreakdown(userId, { accountId: options.accountId, days }),
	]);

	const totals = daily.reduce(accumulate, emptyTotals());

	let targetCounts: AnalyticsData["targetCounts"] = null;
	if (options.accountId) {
		const resolved = await resolveActiveTargets(options.accountId);
		targetCounts = {
			hashtags: resolved.hashtags.length,
			users: resolved.users.length,
			locations: resolved.locations.length,
		};
	}

	return {
		series: buildSeries(daily, days),
		totals,
		accounts,
		breakdown,
		accountId: options.accountId ?? null,
		targetCounts,
	};
}
