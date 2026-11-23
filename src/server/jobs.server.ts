import { and, asc, count, desc, eq, gte, inArray, lte } from "drizzle-orm";

import {
	getDb,
	growthSettings,
	instagramAccounts,
	type Job,
	type JsonObject,
	jobs,
} from "@/db";
import { ensureGrowthSettings } from "./settings.server";
import { resolveActiveTargets } from "./targets.server";

const ROLLING_DAY_MS = 24 * 60 * 60 * 1000;

/* ------------------------------------------------------------------ */
/* Payload building                                                    */
/* ------------------------------------------------------------------ */

export interface GrowthPayload {
	account: { username: string; proxyUrl: string | null };
	settings: {
		likeByTags: boolean;
		followByTags: boolean;
		interactByUsers: boolean;
		unfollowEnabled: boolean;
		watchStories: boolean;
		interactionsPerRun: number;
		runsPerDay: number;
		followPercentage: number;
		commentPercentage: number;
		comments: string[];
		blacklistTags: string[];
		ignoreUsers: string[];
		dontIncludeUsers: string[];
		interactUsers: string[];
		minFollowers: number | null;
		maxFollowers: number | null;
		minFollowing: number | null;
		maxFollowing: number | null;
		maxPostAgeDays: number | null;
		skipPrivateAccounts: boolean;
		actionDelayMinSec: number;
		actionDelayMaxSec: number;
		likesPerDay: number;
		followsPerDay: number;
		unfollowsPerDay: number;
		commentsPerDay: number;
		storiesPerDay: number;
	};
	targets: { hashtags: string[]; users: string[]; locations: string[] };
}

export async function buildGrowthPayload(
	accountId: string,
): Promise<GrowthPayload | null> {
	const db = getDb();
	const accountRows = await db
		.select({
			username: instagramAccounts.username,
			proxyUrl: instagramAccounts.proxyUrl,
		})
		.from(instagramAccounts)
		.where(eq(instagramAccounts.id, accountId))
		.limit(1);
	const account = accountRows[0];
	if (!account) return null;

	const settings = await ensureGrowthSettings(accountId);
	const resolved = await resolveActiveTargets(accountId);

	return {
		account: { username: account.username, proxyUrl: account.proxyUrl },
		settings: {
			likeByTags: settings.likeByTags,
			followByTags: settings.followByTags,
			interactByUsers: settings.interactByUsers,
			unfollowEnabled: settings.unfollowEnabled,
			watchStories: settings.watchStories,
			interactionsPerRun: settings.interactionsPerRun,
			runsPerDay: settings.runsPerDay,
			followPercentage: settings.followPercentage,
			commentPercentage: settings.commentPercentage,
			comments: settings.comments,
			blacklistTags: settings.blacklistTags,
			ignoreUsers: settings.ignoreUsers,
			dontIncludeUsers: settings.dontIncludeUsers,
			interactUsers: settings.interactUsers,
			minFollowers: settings.minFollowers,
			maxFollowers: settings.maxFollowers,
			minFollowing: settings.minFollowing,
			maxFollowing: settings.maxFollowing,
			maxPostAgeDays: settings.maxPostAgeDays,
			skipPrivateAccounts: settings.skipPrivateAccounts,
			actionDelayMinSec: settings.actionDelayMinSec,
			actionDelayMaxSec: settings.actionDelayMaxSec,
			likesPerDay: settings.likesPerDay,
			followsPerDay: settings.followsPerDay,
			unfollowsPerDay: settings.unfollowsPerDay,
			commentsPerDay: settings.commentsPerDay,
			storiesPerDay: settings.storiesPerDay,
		},
		targets: resolved,
	};
}

/* ------------------------------------------------------------------ */
/* Enqueue / manage                                                    */
/* ------------------------------------------------------------------ */

export async function enqueueJob(
	userId: string,
	accountId: string,
	type: "growth_run" | "account_sync" | "login_check",
	options: { scheduledFor?: Date; priority?: number } = {},
): Promise<Job> {
	const db = getDb();

	// Avoid piling up duplicate work for the same account + type.
	const active = await db
		.select({ id: jobs.id })
		.from(jobs)
		.where(
			and(
				eq(jobs.accountId, accountId),
				eq(jobs.type, type),
				inArray(jobs.status, ["queued", "running"]),
			),
		)
		.limit(1);
	if (active[0] && type !== "login_check") {
		const existing = await db
			.select()
			.from(jobs)
			.where(eq(jobs.id, active[0].id))
			.limit(1);
		if (existing[0]) return existing[0];
	}

	const payload =
		type === "growth_run"
			? (((await buildGrowthPayload(accountId)) as unknown as JsonObject) ?? {})
			: {};

	const inserted = await db
		.insert(jobs)
		.values({
			userId,
			accountId,
			type,
			payload,
			priority: options.priority ?? 0,
			scheduledFor: options.scheduledFor ?? new Date(),
		})
		.returning();
	return inserted[0];
}

export async function listJobsForUser(
	userId: string,
	limit = 50,
): Promise<Job[]> {
	const db = getDb();
	return db
		.select()
		.from(jobs)
		.where(eq(jobs.userId, userId))
		.orderBy(desc(jobs.createdAt))
		.limit(limit);
}

export async function listJobsForAccount(
	userId: string,
	accountId: string,
	limit = 25,
): Promise<Job[]> {
	const db = getDb();
	return db
		.select()
		.from(jobs)
		.where(and(eq(jobs.userId, userId), eq(jobs.accountId, accountId)))
		.orderBy(desc(jobs.createdAt))
		.limit(limit);
}

export async function cancelJob(userId: string, jobId: string): Promise<void> {
	const db = getDb();
	await db
		.update(jobs)
		.set({ status: "canceled", finishedAt: new Date(), updatedAt: new Date() })
		.where(
			and(
				eq(jobs.id, jobId),
				eq(jobs.userId, userId),
				inArray(jobs.status, ["queued", "running"]),
			),
		);
}

/* ------------------------------------------------------------------ */
/* Scheduler                                                           */
/* ------------------------------------------------------------------ */

const WEEKDAY_INDEX: Record<string, number> = {
	Sun: 0,
	Mon: 1,
	Tue: 2,
	Wed: 3,
	Thu: 4,
	Fri: 5,
	Sat: 6,
};

export function getZonedParts(
	date: Date,
	timeZone: string,
): { hour: number; weekday: number } {
	try {
		const formatter = new Intl.DateTimeFormat("en-US", {
			timeZone,
			hour: "numeric",
			hour12: false,
			weekday: "short",
		});
		const parts = formatter.formatToParts(date);
		const hour = Number(parts.find((part) => part.type === "hour")?.value ?? 0);
		const weekdayLabel = parts.find((part) => part.type === "weekday")?.value;
		return {
			hour: hour === 24 ? 0 : hour,
			weekday: weekdayLabel ? (WEEKDAY_INDEX[weekdayLabel] ?? 0) : 0,
		};
	} catch {
		return { hour: date.getUTCHours(), weekday: date.getUTCDay() };
	}
}

/**
 * Create `growth_run` jobs for every account that is due for another run.
 * Called lazily by the worker claim endpoint, so no external cron is needed.
 */
export async function ensureScheduledJobs(): Promise<number> {
	const db = getDb();
	const candidates = await db
		.select({
			accountId: instagramAccounts.id,
			userId: instagramAccounts.userId,
			settings: growthSettings,
		})
		.from(instagramAccounts)
		.innerJoin(
			growthSettings,
			eq(growthSettings.accountId, instagramAccounts.id),
		)
		.where(
			and(
				eq(instagramAccounts.status, "active"),
				eq(growthSettings.enabled, true),
			),
		);

	const now = new Date();
	let created = 0;

	for (const candidate of candidates) {
		const settings = candidate.settings;
		if (settings.runsPerDay <= 0) continue;

		const { hour, weekday } = getZonedParts(now, settings.timezone);
		if (!settings.daysOfWeek.includes(weekday)) continue;

		const withinHours =
			settings.workingHoursStart <= settings.workingHoursEnd
				? hour >= settings.workingHoursStart && hour < settings.workingHoursEnd
				: hour >= settings.workingHoursStart || hour < settings.workingHoursEnd;
		if (!withinHours) continue;

		const [recent] = await db
			.select({ value: count() })
			.from(jobs)
			.where(
				and(
					eq(jobs.accountId, candidate.accountId),
					eq(jobs.type, "growth_run"),
					gte(jobs.createdAt, new Date(now.getTime() - ROLLING_DAY_MS)),
				),
			);
		if ((recent?.value ?? 0) >= settings.runsPerDay) continue;

		const [lastJob] = await db
			.select({ createdAt: jobs.createdAt })
			.from(jobs)
			.where(
				and(
					eq(jobs.accountId, candidate.accountId),
					eq(jobs.type, "growth_run"),
				),
			)
			.orderBy(desc(jobs.createdAt))
			.limit(1);

		if (lastJob) {
			const activeWindowHours =
				settings.workingHoursStart <= settings.workingHoursEnd
					? settings.workingHoursEnd - settings.workingHoursStart
					: 24 - settings.workingHoursStart + settings.workingHoursEnd;
			const spacingMs =
				(Math.max(activeWindowHours, 1) * 60 * 60 * 1000) / settings.runsPerDay;
			if (now.getTime() - lastJob.createdAt.getTime() < spacingMs) continue;
		}

		await enqueueJob(candidate.userId, candidate.accountId, "growth_run");
		created += 1;
	}

	return created;
}

/* ------------------------------------------------------------------ */
/* Worker claims                                                       */
/* ------------------------------------------------------------------ */

/** Atomically claim the next due job using SKIP LOCKED. */
export async function claimNextJob(workerName: string): Promise<Job | null> {
	const db = getDb();
	return db.transaction(async (tx) => {
		const rows = await tx
			.select()
			.from(jobs)
			.where(and(eq(jobs.status, "queued"), lte(jobs.scheduledFor, new Date())))
			.orderBy(desc(jobs.priority), asc(jobs.scheduledFor))
			.limit(1)
			.for("update", { skipLocked: true });

		const job = rows[0];
		if (!job) return null;

		const updated = await tx
			.update(jobs)
			.set({
				status: "running",
				lockedAt: new Date(),
				lockedBy: workerName,
				startedAt: new Date(),
				attempts: job.attempts + 1,
				updatedAt: new Date(),
			})
			.where(eq(jobs.id, job.id))
			.returning();
		return updated[0] ?? null;
	});
}

export async function updateJobProgress(
	jobId: string,
	progress: number,
): Promise<void> {
	const db = getDb();
	await db
		.update(jobs)
		.set({
			progress: Math.max(0, Math.min(100, progress)),
			updatedAt: new Date(),
		})
		.where(eq(jobs.id, jobId));
}

/** Requeue stuck jobs whose worker stopped heartbeating. */
export async function requeueStaleJobs(olderThanMinutes = 30): Promise<number> {
	const db = getDb();
	const cutoff = new Date(Date.now() - olderThanMinutes * 60 * 1000);
	const rows = await db
		.update(jobs)
		.set({
			status: "queued",
			lockedAt: null,
			lockedBy: null,
			updatedAt: new Date(),
			error: "Requeued after worker timeout",
		})
		.where(and(eq(jobs.status, "running"), lte(jobs.lockedAt, cutoff)))
		.returning({ id: jobs.id });
	return rows.length;
}

export async function listQueuedJobs(limit = 50): Promise<Job[]> {
	const db = getDb();
	return db
		.select()
		.from(jobs)
		.where(inArray(jobs.status, ["queued", "running"]))
		.orderBy(asc(jobs.scheduledFor))
		.limit(limit);
}

export async function getJobById(jobId: string): Promise<Job | null> {
	const db = getDb();
	const rows = await db.select().from(jobs).where(eq(jobs.id, jobId)).limit(1);
	return rows[0] ?? null;
}

export async function countJobsByStatus(): Promise<Record<string, number>> {
	const db = getDb();
	const rows = await db
		.select({ status: jobs.status, value: count() })
		.from(jobs)
		.groupBy(jobs.status);
	return Object.fromEntries(rows.map((row) => [row.status, Number(row.value)]));
}
