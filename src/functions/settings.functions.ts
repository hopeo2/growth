import { createServerFn } from "@tanstack/react-start";

import { authMiddleware } from "@/lib/auth-middleware";
import { accountIdSchema, growthSettingsSchema } from "@/lib/schemas";
import * as settingsService from "@/server/settings.server";

export const getGrowthSettingsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(accountIdSchema)
	.handler(async ({ data, context }) =>
		settingsService.getGrowthSettings(context.profile.id, data.accountId),
	);

export const saveGrowthSettingsFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(growthSettingsSchema)
	.handler(async ({ data, context }) =>
		settingsService.saveGrowthSettings(context.profile.id, data),
	);
