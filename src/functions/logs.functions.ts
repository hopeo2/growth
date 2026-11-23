import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

import { authMiddleware } from "@/lib/auth-middleware";
import * as logsService from "@/server/logs.server";

const activityQuerySchema = z.object({
	accountId: z.string().uuid().optional(),
	actions: z
		.array(
			z.enum([
				"like",
				"follow",
				"unfollow",
				"comment",
				"story",
				"login",
				"info",
				"warning",
				"error",
			]),
		)
		.optional(),
	limit: z.number().int().min(1).max(500).default(150),
});

export const listActivityLogsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(activityQuerySchema)
	.handler(async ({ data, context }) =>
		logsService.listActivityLogs(context.profile.id, data),
	);

const dailyStatsQuerySchema = z.object({
	accountId: z.string().uuid().optional(),
	days: z.number().int().min(1).max(365).default(30),
});

export const listDailyStatsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(dailyStatsQuerySchema)
	.handler(async ({ data, context }) =>
		logsService.listDailyStats(context.profile.id, data),
	);
