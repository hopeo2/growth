import { z } from "zod";

/* ------------------------------------------------------------------ */
/* Reusable field schemas                                              */
/* ------------------------------------------------------------------ */

export const instagramUsername = z
	.string()
	.trim()
	.min(1, "Username is required")
	.max(30)
	.regex(/^[A-Za-z0-9._]+$/, "Only letters, numbers, dots and underscores");

export const hashtagValue = z
	.string()
	.trim()
	.min(1, "Hashtag is required")
	.max(100)
	.transform((value) => value.replace(/^#+/, "").toLowerCase())
	.refine((value) => /^[a-z0-9_]+$/.test(value), {
		message: "Hashtags may only contain letters, numbers and underscores",
	});

export const proxyUrl = z
	.string()
	.trim()
	.max(300)
	.optional()
	.transform((value) => (value ? value : null))
	.refine((value) => value === null || /^(https?|socks5):\/\//.test(value), {
		message: "Proxy must start with http://, https:// or socks5://",
	});

const stringList = (max: number, itemMax = 100) =>
	z
		.array(z.string().trim().min(1).max(itemMax))
		.max(max)
		.transform((items) => Array.from(new Set(items)));

/* ------------------------------------------------------------------ */
/* Accounts                                                            */
/* ------------------------------------------------------------------ */

export const createAccountSchema = z.object({
	username: instagramUsername,
	password: z.string().min(1, "Password is required").max(200),
	proxyUrl,
});

export const updateAccountSchema = z.object({
	accountId: z.string().uuid(),
	proxyUrl,
	status: z.enum(["active", "paused"]).optional(),
});

export const accountIdSchema = z.object({ accountId: z.string().uuid() });

export const updateAccountCredentialsSchema = z.object({
	accountId: z.string().uuid(),
	password: z.string().min(1).max(200),
});

/* ------------------------------------------------------------------ */
/* Growth settings                                                     */
/* ------------------------------------------------------------------ */

export const growthSettingsSchema = z.object({
	accountId: z.string().uuid(),
	enabled: z.boolean(),

	likeByTags: z.boolean(),
	followByTags: z.boolean(),
	interactByUsers: z.boolean(),
	unfollowEnabled: z.boolean(),
	watchStories: z.boolean(),

	runsPerDay: z.number().int().min(0).max(96),
	likesPerDay: z.number().int().min(0).max(2000),
	followsPerDay: z.number().int().min(0).max(1000),
	unfollowsPerDay: z.number().int().min(0).max(1000),
	commentsPerDay: z.number().int().min(0).max(500),
	storiesPerDay: z.number().int().min(0).max(500),

	interactionsPerRun: z.number().int().min(1).max(500),
	followPercentage: z.number().int().min(0).max(100),
	commentPercentage: z.number().int().min(0).max(100),
	comments: stringList(50, 220),

	blacklistTags: stringList(100),
	ignoreUsers: stringList(200, 40),
	dontIncludeUsers: stringList(200, 40),
	interactUsers: stringList(200, 40),
	minFollowers: z.number().int().min(0).max(100_000_000).nullable(),
	maxFollowers: z.number().int().min(0).max(100_000_000).nullable(),
	minFollowing: z.number().int().min(0).max(100_000_000).nullable(),
	maxFollowing: z.number().int().min(0).max(100_000_000).nullable(),
	maxPostAgeDays: z.number().int().min(1).max(3650).nullable(),
	skipPrivateAccounts: z.boolean(),

	actionDelayMinSec: z.number().int().min(1).max(600),
	actionDelayMaxSec: z.number().int().min(1).max(600),
	workingHoursStart: z.number().int().min(0).max(23),
	workingHoursEnd: z.number().int().min(0).max(23),
	daysOfWeek: z.array(z.number().int().min(0).max(6)).max(7),
	timezone: z.string().min(1).max(60),
});

/* ------------------------------------------------------------------ */
/* Targets                                                             */
/* ------------------------------------------------------------------ */

export const addTargetSchema = z.object({
	accountId: z.string().uuid(),
	kind: z.enum(["hashtag", "username", "location"]),
	value: z.string().trim().min(1).max(100),
});

export const removeTargetSchema = z.object({
	accountId: z.string().uuid(),
	targetId: z.string().uuid(),
});

export const toggleTargetSchema = z.object({
	accountId: z.string().uuid(),
	targetId: z.string().uuid(),
	enabled: z.boolean(),
});

/* ------------------------------------------------------------------ */
/* Jobs                                                                */
/* ------------------------------------------------------------------ */

export const enqueueJobSchema = z.object({
	accountId: z.string().uuid(),
	type: z
		.enum(["growth_run", "account_sync", "login_check"])
		.default("growth_run"),
});

export const jobIdSchema = z.object({ jobId: z.string().uuid() });

/* ------------------------------------------------------------------ */
/* Admin                                                              */
/* ------------------------------------------------------------------ */

export const adminUserActionSchema = z.object({
	userId: z.string().uuid(),
	action: z.enum(["suspend", "activate", "promote", "demote"]),
});

export const adminAccountActionSchema = z.object({
	accountId: z.string().uuid(),
	action: z.enum(["pause", "activate", "reset_error"]),
});

export const serviceSettingsSchema = z.object({
	workerEnabled: z.boolean(),
	maintenanceMode: z.boolean(),
	registrationOpen: z.boolean(),
	maxAccountsPerUser: z.number().int().min(0).max(100),
	defaultLikesPerDay: z.number().int().min(0).max(2000),
	defaultFollowsPerDay: z.number().int().min(0).max(1000),
	defaultUnfollowsPerDay: z.number().int().min(0).max(1000),
	defaultCommentsPerDay: z.number().int().min(0).max(500),
});
