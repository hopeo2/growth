import { createFileRoute } from "@tanstack/react-router";
import { eq } from "drizzle-orm";
import type { JsonObject } from "@/db";
import { getDb, instagramAccounts } from "@/db";
import { safeEqual } from "@/lib/crypto.server";
import { serverEnv } from "@/lib/env.server";
import * as jobsService from "@/server/jobs.server";
import * as logsService from "@/server/logs.server";
import * as statsService from "@/server/stats.server";
import * as workersService from "@/server/workers.server";

const ACTIONS = new Set([
	"like",
	"follow",
	"unfollow",
	"comment",
	"story",
	"login",
	"info",
	"warning",
	"error",
]);

type ActivityAction = Parameters<
	typeof logsService.ingestActivityBatch
>[3][number]["action"];

function unauthorized(): Response {
	return new Response(JSON.stringify({ error: "Unauthorized" }), {
		status: 401,
		headers: { "Content-Type": "application/json" },
	});
}

function badRequest(message: string): Response {
	return new Response(JSON.stringify({ error: message }), {
		status: 400,
		headers: { "Content-Type": "application/json" },
	});
}

function asNumber(value: unknown): number | undefined {
	if (typeof value === "number" && Number.isFinite(value))
		return Math.round(value);
	if (typeof value === "string" && value.trim() !== "") {
		const parsed = Number(value);
		if (Number.isFinite(parsed)) return Math.round(parsed);
	}
	return undefined;
}

function sanitizeStats(raw: unknown) {
	const source = (raw ?? {}) as Record<string, unknown>;
	return {
		likes: asNumber(source.likes),
		follows: asNumber(source.follows),
		unfollows: asNumber(source.unfollows),
		comments: asNumber(source.comments),
		stories: asNumber(source.stories),
		errors: asNumber(source.errors),
	};
}

/**
 * Worker API. The Python automation worker authenticates with a shared bearer
 * token (`WORKER_API_TOKEN`) and drives the job lifecycle here.
 */
export const Route = createFileRoute("/api/worker/$action")({
	server: {
		handlers: {
			POST: async ({ request, params }) => {
				const header = request.headers.get("authorization") ?? "";
				const token = header.startsWith("Bearer ")
					? header.slice(7).trim()
					: "";

				let expected: string;
				try {
					expected = serverEnv.workerApiToken;
				} catch {
					return new Response(
						JSON.stringify({ error: "Worker API is not configured" }),
						{ status: 503, headers: { "Content-Type": "application/json" } },
					);
				}
				if (!token || !safeEqual(token, expected)) return unauthorized();

				const body = (await request.json().catch(() => ({}))) as Record<
					string,
					unknown
				>;
				const workerName =
					typeof body.worker === "string" && body.worker
						? body.worker
						: "worker";

				switch (params.action) {
					case "heartbeat": {
						await workersService.registerHeartbeat(
							{
								name: workerName,
								version:
									typeof body.version === "string" ? body.version : undefined,
								concurrency: asNumber(body.concurrency) ?? 1,
							},
							{
								status: (body.status as "online" | "idle" | "busy") ?? "online",
								currentJobId:
									typeof body.currentJobId === "string"
										? body.currentJobId
										: null,
							},
						);
						return Response.json({
							ok: true,
							serverTime: new Date().toISOString(),
						});
					}

					case "schedule": {
						const created = await jobsService.ensureScheduledJobs();
						const requeued = await jobsService.requeueStaleJobs();
						return Response.json({ ok: true, created, requeued });
					}

					case "claim": {
						await jobsService.ensureScheduledJobs();
						const job = await jobsService.claimNextJob(workerName);
						if (!job) return Response.json({ job: null });

						const rows = await getDb()
							.select({
								id: instagramAccounts.id,
								username: instagramAccounts.username,
								proxyUrl: instagramAccounts.proxyUrl,
								credentials: instagramAccounts.credentials,
							})
							.from(instagramAccounts)
							.where(eq(instagramAccounts.id, job.accountId))
							.limit(1);

						await workersService.registerHeartbeat(
							{ name: workerName },
							{ status: "busy", currentJobId: job.id },
						);

						return Response.json({ job, account: rows[0] ?? null });
					}

					case "progress": {
						const jobId = typeof body.jobId === "string" ? body.jobId : "";
						if (!jobId) return badRequest("jobId is required");
						await jobsService.updateJobProgress(
							jobId,
							asNumber(body.progress) ?? 0,
						);
						return Response.json({ ok: true });
					}

					case "events": {
						const jobId = typeof body.jobId === "string" ? body.jobId : "";
						if (!jobId) return badRequest("jobId is required");
						const job = await jobsService.getJobById(jobId);
						if (!job) return badRequest("Unknown job");

						const rawEvents = Array.isArray(body.events) ? body.events : [];
						const events = rawEvents
							.map((entry) => {
								const item = (entry ?? {}) as Record<string, unknown>;
								const action = String(item.action ?? "info");
								if (!ACTIONS.has(action)) return null;
								return {
									action: action as ActivityAction,
									target: typeof item.target === "string" ? item.target : null,
									message:
										typeof item.message === "string" ? item.message : null,
									detail:
										item.detail && typeof item.detail === "object"
											? (item.detail as JsonObject)
											: null,
								};
							})
							.filter(
								(entry): entry is NonNullable<typeof entry> => entry !== null,
							);

						const inserted = await logsService.ingestActivityBatch(
							job.userId,
							job.accountId,
							job.id,
							events,
						);
						return Response.json({ ok: true, inserted });
					}

					case "complete": {
						const jobId = typeof body.jobId === "string" ? body.jobId : "";
						if (!jobId) return badRequest("jobId is required");
						const job = await jobsService.getJobById(jobId);
						if (!job) return badRequest("Unknown job");

						const rawReport = (body.report ?? {}) as Record<string, unknown>;
						await statsService.applyJobSuccess(job, {
							stats: sanitizeStats(rawReport.stats),
							followers: asNumber(rawReport.followers),
							following: asNumber(rawReport.following),
							posts: asNumber(rawReport.posts),
							result:
								rawReport.result && typeof rawReport.result === "object"
									? (rawReport.result as JsonObject)
									: {},
						});
						await workersService.registerHeartbeat(
							{ name: workerName },
							{ status: "idle", currentJobId: null },
						);
						return Response.json({ ok: true });
					}

					case "fail": {
						const jobId = typeof body.jobId === "string" ? body.jobId : "";
						if (!jobId) return badRequest("jobId is required");
						const job = await jobsService.getJobById(jobId);
						if (!job) return badRequest("Unknown job");

						const message =
							typeof body.error === "string" && body.error
								? body.error
								: "Worker reported an unknown error";
						const outcome = await statsService.applyJobFailure(job, message);
						await workersService.registerHeartbeat(
							{ name: workerName },
							{ status: "idle", currentJobId: null },
						);
						return Response.json({ ok: true, outcome });
					}

					default:
						return new Response(JSON.stringify({ error: "Unknown action" }), {
							status: 404,
							headers: { "Content-Type": "application/json" },
						});
				}
			},
		},
	},
});
