import { count, desc, eq, gte, ilike, inArray, or } from "drizzle-orm";

import {
	accountStatsDaily,
	getDb,
	instagramAccounts,
	type Job,
	jobs,
	type Profile,
	profiles,
} from "@/db";
import { countJobsByStatus } from "./jobs.server";
import { listWorkers } from "./workers.server";

export interface AdminOverview {
	userCount: number;
	activeUserCount: number;
	suspendedUserCount: number;
	adminCount: number;
	accountCount: number;
	activeAccountCount: number;
	errorAccountCount: number;
	interactions30d: number;
	jobCounts: Record<string, number>;
	workers: Awaited<ReturnType<typeof listWorkers>>;
	recentUsers: Profile[];
	newUsers7d: number;
}

export async function getAdminOverview(): Promise<AdminOverview> {
	const db = getDb();

	const [
		userRows,
		accountRows,
		interactions,
		jobCounts,
		workers,
		recentUsers,
		newUsers,
	] = await Promise.all([
		db
			.select({ status: profiles.status, role: profiles.role, value: count() })
			.from(profiles)
			.groupBy(profiles.status, profiles.role),
		db
			.select({ status: instagramAccounts.status, value: count() })
			.from(instagramAccounts)
			.groupBy(instagramAccounts.status),
		db
			.select({
				likes: accountStatsDaily.likes,
				follows: accountStatsDaily.follows,
				comments: accountStatsDaily.comments,
				stories: accountStatsDaily.stories,
			})
			.from(accountStatsDaily)
			.where(
				gte(
					accountStatsDaily.day,
					new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
						.toISOString()
						.slice(0, 10),
				),
			),
		countJobsByStatus(),
		listWorkers(),
		db.select().from(profiles).orderBy(desc(profiles.createdAt)).limit(10),
		db
			.select({ value: count() })
			.from(profiles)
			.where(
				gte(profiles.createdAt, new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)),
			),
	]);

	let userCount = 0;
	let activeUserCount = 0;
	let suspendedUserCount = 0;
	let adminCount = 0;
	for (const row of userRows) {
		const value = Number(row.value);
		userCount += value;
		if (row.status === "active") activeUserCount += value;
		if (row.status === "suspended") suspendedUserCount += value;
		if (row.role === "admin") adminCount += value;
	}

	let accountCount = 0;
	let activeAccountCount = 0;
	let errorAccountCount = 0;
	for (const row of accountRows) {
		const value = Number(row.value);
		accountCount += value;
		if (row.status === "active") activeAccountCount += value;
		if (row.status === "error") errorAccountCount += value;
	}

	const interactions30d = interactions.reduce(
		(sum, row) => sum + row.likes + row.follows + row.comments + row.stories,
		0,
	);

	return {
		userCount,
		activeUserCount,
		suspendedUserCount,
		adminCount,
		accountCount,
		activeAccountCount,
		errorAccountCount,
		interactions30d,
		jobCounts,
		workers,
		recentUsers,
		newUsers7d: Number(newUsers[0]?.value ?? 0),
	};
}

export async function listAllUsers(
	query?: string,
): Promise<Array<Profile & { accountCount: number }>> {
	const db = getDb();
	const filter = query
		? or(
				ilike(profiles.email, `%${query}%`),
				ilike(profiles.displayName, `%${query}%`),
			)
		: undefined;

	const users = await db
		.select()
		.from(profiles)
		.where(filter)
		.orderBy(desc(profiles.createdAt))
		.limit(200);

	const counts = await db
		.select({ userId: instagramAccounts.userId, value: count() })
		.from(instagramAccounts)
		.groupBy(instagramAccounts.userId);
	const countMap = new Map(
		counts.map((row) => [row.userId, Number(row.value)]),
	);

	return users.map((user) => ({
		...user,
		accountCount: countMap.get(user.id) ?? 0,
	}));
}

export async function listAllAccounts() {
	const db = getDb();
	return db
		.select({
			id: instagramAccounts.id,
			username: instagramAccounts.username,
			userId: instagramAccounts.userId,
			status: instagramAccounts.status,
			followers: instagramAccounts.followers,
			lastError: instagramAccounts.lastError,
			lastRunAt: instagramAccounts.lastRunAt,
			createdAt: instagramAccounts.createdAt,
			ownerEmail: profiles.email,
		})
		.from(instagramAccounts)
		.leftJoin(profiles, eq(profiles.id, instagramAccounts.userId))
		.orderBy(desc(instagramAccounts.createdAt))
		.limit(200);
}

export async function listAllJobs(limit = 100): Promise<Job[]> {
	const db = getDb();
	return db.select().from(jobs).orderBy(desc(jobs.createdAt)).limit(limit);
}

export async function applyUserAction(
	userId: string,
	action: "suspend" | "activate" | "promote" | "demote",
): Promise<void> {
	const db = getDb();
	const patch =
		action === "suspend"
			? { status: "suspended" as const }
			: action === "activate"
				? { status: "active" as const }
				: action === "promote"
					? { role: "admin" as const }
					: { role: "user" as const };

	await db
		.update(profiles)
		.set({ ...patch, updatedAt: new Date() })
		.where(eq(profiles.id, userId));
}

export async function applyAccountAction(
	accountId: string,
	action: "pause" | "activate" | "reset_error",
): Promise<void> {
	const db = getDb();
	const patch =
		action === "pause"
			? { status: "paused" as const }
			: { status: "active" as const, lastError: null };

	await db
		.update(instagramAccounts)
		.set({ ...patch, updatedAt: new Date() })
		.where(eq(instagramAccounts.id, accountId));
}

export async function forceJobAction(
	jobId: string,
	action: "retry" | "cancel",
): Promise<void> {
	const db = getDb();
	if (action === "cancel") {
		await db
			.update(jobs)
			.set({
				status: "canceled",
				finishedAt: new Date(),
				updatedAt: new Date(),
			})
			.where(eq(jobs.id, jobId));
		return;
	}
	await db
		.update(jobs)
		.set({
			status: "queued",
			attempts: 0,
			error: null,
			lockedAt: null,
			lockedBy: null,
			scheduledFor: new Date(),
			updatedAt: new Date(),
		})
		.where(eq(jobs.id, jobId));
}

export async function countOpenJobs(): Promise<number> {
	const db = getDb();
	const rows = await db
		.select({ value: count() })
		.from(jobs)
		.where(inArray(jobs.status, ["queued", "running"]));
	return Number(rows[0]?.value ?? 0);
}
