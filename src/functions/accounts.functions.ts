import { createServerFn } from "@tanstack/react-start";

import { authMiddleware } from "@/lib/auth-middleware";
import {
	accountIdSchema,
	createAccountSchema,
	updateAccountCredentialsSchema,
	updateAccountSchema,
} from "@/lib/schemas";
import * as accountService from "@/server/accounts.server";

export const listAccountsFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.handler(async ({ context }) =>
		accountService.listAccounts(context.profile.id),
	);

export const getAccountFn = createServerFn({ method: "GET" })
	.middleware([authMiddleware])
	.validator(accountIdSchema)
	.handler(async ({ data, context }) =>
		accountService.getAccountSummary(context.profile.id, data.accountId),
	);

export const createAccountFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(createAccountSchema)
	.handler(async ({ data, context }) =>
		accountService.createAccount(context.profile.id, data),
	);

export const updateAccountFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(updateAccountSchema)
	.handler(async ({ data, context }) => {
		await accountService.updateAccount(context.profile.id, data);
		return { ok: true };
	});

export const updateAccountCredentialsFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(updateAccountCredentialsSchema)
	.handler(async ({ data, context }) => {
		await accountService.updateAccountPassword(context.profile.id, data);
		return { ok: true };
	});

export const deleteAccountFn = createServerFn({ method: "POST" })
	.middleware([authMiddleware])
	.validator(accountIdSchema)
	.handler(async ({ data, context }) => {
		await accountService.deleteAccount(context.profile.id, data.accountId);
		return { ok: true };
	});
