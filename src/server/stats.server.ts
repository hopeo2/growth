import { eq, sql } from "drizzle-orm";

import {
	accountStatsDaily,
	getDb,
	instagramAccounts,
	type Job,
	type JsonObject,
	jobs,
	type Transaction,
} from "@/db";
import { logActivity } from "./logs.server";

export type JobStats = {
	likes?: number;
	follows?: number;
	unfollows?: number;
	comments?: number;
	stories?: number;
	errors?: number;
};

export type JobReport = {
	stats?: JobStats;
	followers?: number;
	following?: number;
	posts?: number;
	result?: JsonObject;
};

function todayUtc(): string {
	return new Date().toISOString().slice(0, 10);
}

async function upsertDailyStats(
	tx: Transaction,
	params: {
		userId: string;
		accountId: string;
		stats: JobStats;
		followers?: number;
		following?: number;
		posts?: number;
	},
) {
	const { stats } = params;
	const set: Record<string, unknown> = {
		likes: sql`${accountStatsDaily.likes} + ${stats.likes ?? 0}`,
		follows: sql`${accountStatsDaily.follows} + ${stats.follows ?? 0}`,
		unfollows: sql`${accountStatsDaily.unfollows} + ${stats.unfollows ?? 0}`,
		comments: sql`${accountStatsDaily.comments} + ${stats.comments ?? 0}`,
		stories: sql`${accountStatsDaily.stories} + ${stats.stories ?? 0}`,
		errors: sql`${accountStatsDaily.errors} + ${stats.errors ?? 0}`,
		updatedAt: new Date(),
	};
	if (typeof params.followers === "number") set.followers = params.followers;
	if (typeof params.following === "number") set.following = params.following;
	if (typeof params.posts === "number") set.posts = params.posts;

	await tx
		.insert(accountStatsDaily)
		.values({
			userId: params.userId,
			accountId: params.accountId,
			day: todayUtc(),
			likes: stats.likes ?? 0,
			follows: stats.follows ?? 0,
			unfollows: stats.unfollows ?? 0,
			comments: stats.comments ?? 0,
			stories: stats.stories ?? 0,
			errors: stats.errors ?? 0,
			followers: params.followers,
			following: params.following,
			posts: params.posts,
		})
		.onConflictDoUpdate({
			target: [accountStatsDaily.accountId, accountStatsDaily.day],
			set,
		});
}

/** Mark a job succeeded and fold its reported stats into the account. */
export async function applyJobSuccess(
	job: Job,
	report: JobReport,
): Promise<void> {
	const db = getDb();
	const stats = report.stats ?? {};

	await db.transaction(async (tx) => {
		await tx
			.update(jobs)
			.set({
				status: "succeeded",
				progress: 100,
				finishedAt: new Date(),
				updatedAt: new Date(),
				error: null,
				result: { ...(report.result ?? {}), stats },
			})
			.where(eq(jobs.id, job.id));

		await tx
			.update(instagramAccounts)
			.set({
				status: "active",
				lastRunAt: new Date(),
				lastLoginAt: job.type === "login_check" ? new Date() : undefined,
				lastError: null,
				...(typeof report.followers === "number"
					? { followers: report.followers }
					: {}),
				...(typeof report.following === "number"
					? { following: report.following }
					: {}),
				...(typeof report.posts === "number" ? { posts: report.posts } : {}),
				updatedAt: new Date(),
			})
			.where(eq(instagramAccounts.id, job.accountId));

		await upsertDailyStats(tx, {
			userId: job.userId,
			accountId: job.accountId,
			stats,
			followers: report.followers,
			following: report.following,
			posts: report.posts,
		});
	});

	await logActivity({
		userId: job.userId,
		accountId: job.accountId,
		jobId: job.id,
		action: "info",
		message: `Job ${job.type} completed`,
		detail: { stats, result: report.result ?? {} },
	});
}

/** Record a failure; retry while attempts remain, otherwise mark failed. */
export async function applyJobFailure(
	job: Job,
	message: string,
): Promise<"queued" | "failed"> {
	const db = getDb();
	const canRetry = job.attempts < job.maxAttempts;
	const trimmed = message.slice(0, 2000);

	if (canRetry) {
		const backoffMs = 60_000 * Math.max(1, job.attempts);
		await db
			.update(jobs)
			.set({
				status: "queued",
				lockedAt: null,
				lockedBy: null,
				error: trimmed,
				scheduledFor: new Date(Date.now() + backoffMs),
				updatedAt: new Date(),
			})
			.where(eq(jobs.id, job.id));
		await logActivity({
			userId: job.userId,
			accountId: job.accountId,
			jobId: job.id,
			action: "warning",
			message: `Job ${job.type} failed, retrying: ${trimmed}`,
		});
		return "queued";
	}

	await db.transaction(async (tx) => {
		await tx
			.update(jobs)
			.set({
				status: "failed",
				finishedAt: new Date(),
				updatedAt: new Date(),
				error: trimmed,
			})
			.where(eq(jobs.id, job.id));

		await tx
			.update(instagramAccounts)
			.set({
				status: "error",
				lastError: trimmed,
				lastRunAt: new Date(),
				updatedAt: new Date(),
			})
			.where(eq(instagramAccounts.id, job.accountId));

		await upsertDailyStats(tx, {
			userId: job.userId,
			accountId: job.accountId,
			stats: { errors: 1 },
		});
	});

	await logActivity({
		userId: job.userId,
		accountId: job.accountId,
		jobId: job.id,
		action: "error",
		message: `Job ${job.type} failed: ${trimmed}`,
	});
	return "failed";
}

/** Called when a login_check job proves the credentials work. */
export async function markAccountVerified(
	accountId: string,
	profile: { followers?: number; following?: number; posts?: number } = {},
): Promise<void> {
	const db = getDb();
	await db
		.update(instagramAccounts)
		.set({
			status: "active",
			lastLoginAt: new Date(),
			lastError: null,
			...(typeof profile.followers === "number"
				? { followers: profile.followers }
				: {}),
			...(typeof profile.following === "number"
				? { following: profile.following }
				: {}),
			...(typeof profile.posts === "number" ? { posts: profile.posts } : {}),
			updatedAt: new Date(),
		})
		.where(eq(instagramAccounts.id, accountId));
}
