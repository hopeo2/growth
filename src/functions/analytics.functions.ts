import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { authMiddleware } from "@/lib/auth-middleware";
import * as analyticsService from "@/server/analytics.server";

export const getDashboardFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.handler(async ({ context }) =>
		analyticsService.getDashboard(context.profile.id),
	);

const analyticsQuerySchema = z.object({
	accountId: z.string().uuid().optional(),
	days: z.number().int().min(1).max(365).default(30),
});

export const getAnalyticsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(analyticsQuerySchema)
	.handler(async ({ data, context }) =>
		analyticsService.getAnalytics(context.profile.id, data),
	);

export const getActionBreakdownFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(analyticsQuerySchema)
	.handler(async ({ data, context }) =>
		analyticsService.getActionBreakdown(context.profile.id, data),
	);
