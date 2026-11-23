import { createServerFn } from "@tanstack/react-start";

import { authMiddleware } from "@/lib/auth-middleware";
import { accountIdSchema, enqueueJobSchema, jobIdSchema } from "@/lib/schemas";
import * as jobService from "@/server/jobs.server";

export const enqueueJobFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(enqueueJobSchema)
	.handler(async ({ data, context }) => {
		const job = await jobService.enqueueJob(
			context.profile.id,
			data.accountId,
			data.type,
			{ priority: data.type === "growth_run" ? 0 : 10 },
		);
		return { jobId: job.id };
	});

export const listJobsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.handler(async ({ context }) =>
		jobService.listJobsForUser(context.profile.id),
	);

export const listAccountJobsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(accountIdSchema)
	.handler(async ({ data, context }) =>
		jobService.listJobsForAccount(context.profile.id, data.accountId),
	);

export const cancelJobFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(jobIdSchema)
	.handler(async ({ data, context }) => {
		await jobService.cancelJob(context.profile.id, data.jobId);
		return { ok: true };
	});
