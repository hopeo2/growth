import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

import { adminMiddleware } from "@/lib/auth-middleware";
import {
	adminAccountActionSchema,
	adminUserActionSchema,
	jobIdSchema,
	serviceSettingsSchema,
} from "@/lib/schemas";
import * as adminService from "@/server/admin.server";
import * as serviceService from "@/server/service.server";

export const getAdminOverviewFn = createServerFn({ method: "GET" })
	.middleware([adminMiddleware])
	.handler(async () => adminService.getAdminOverview());

export const listAllUsersFn = createServerFn({ method: "GET" })
	.middleware([adminMiddleware])
	.validator(z.object({ query: z.string().trim().max(100).optional() }))
	.handler(async ({ data }) => adminService.listAllUsers(data.query));

export const listAllAccountsFn = createServerFn({ method: "GET" })
	.middleware([adminMiddleware])
	.handler(async () => adminService.listAllAccounts());

export const listAllJobsFn = createServerFn({ method: "GET" })
	.middleware([adminMiddleware])
	.handler(async () => adminService.listAllJobs());

export const applyUserActionFn = createServerFn({ method: "POST" })
	.middleware([adminMiddleware])
	.validator(adminUserActionSchema)
	.handler(async ({ data, context }) => {
		if (data.userId === context.profile.id) {
			throw new Error("You cannot change your own role or status");
		}
		await adminService.applyUserAction(data.userId, data.action);
		return { ok: true };
	});

export const applyAccountActionFn = createServerFn({ method: "POST" })
	.middleware([adminMiddleware])
	.validator(adminAccountActionSchema)
	.handler(async ({ data }) => {
		await adminService.applyAccountAction(data.accountId, data.action);
		return { ok: true };
	});

export const forceJobActionFn = createServerFn({ method: "POST" })
	.middleware([adminMiddleware])
	.validator(jobIdSchema.extend({ action: z.enum(["retry", "cancel"]) }))
	.handler(async ({ data }) => {
		await adminService.forceJobAction(data.jobId, data.action);
		return { ok: true };
	});

export const getServiceSettingsFn = createServerFn({ method: "GET" })
	.middleware([adminMiddleware])
	.handler(async () => serviceService.getServiceSettings());

export const updateServiceSettingsFn = createServerFn({ method: "POST" })
	.middleware([adminMiddleware])
	.validator(serviceSettingsSchema)
	.handler(async ({ data }) => serviceService.updateServiceSettings(data));
