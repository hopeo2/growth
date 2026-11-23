import { createServerFn } from "@tanstack/react-start";

import { authMiddleware } from "@/lib/auth-middleware";
import {
	accountIdSchema,
	addTargetSchema,
	removeTargetSchema,
	toggleTargetSchema,
} from "@/lib/schemas";
import * as targetService from "@/server/targets.server";

export const listTargetsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(accountIdSchema)
	.handler(async ({ data, context }) =>
		targetService.listTargets(context.profile.id, data.accountId),
	);

export const addTargetFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(addTargetSchema)
	.handler(async ({ data, context }) =>
		targetService.addTarget(context.profile.id, data),
	);

export const removeTargetFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(removeTargetSchema)
	.handler(async ({ data, context }) => {
		await targetService.removeTarget(context.profile.id, data);
		return { ok: true };
	});

export const toggleTargetFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(toggleTargetSchema)
	.handler(async ({ data, context }) => {
		await targetService.toggleTarget(context.profile.id, data);
		return { ok: true };
	});
