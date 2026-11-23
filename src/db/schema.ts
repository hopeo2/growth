import {
	boolean,
	date,
	index,
	integer,
	jsonb,
	pgEnum,
	pgTable,
	text,
	timestamp,
	uniqueIndex,
	uuid,
} from "drizzle-orm/pg-core";

/**
 * JSON types that are compatible with TanStack Start's server-function
 * serializability check (which rejects bare `unknown`/`Record<string, unknown>`).
 */
export type JsonValue =
	| string
	| number
	| boolean
	| null
	| JsonValue[]
	| { [key: string]: JsonValue };

export type JsonObject = { [key: string]: JsonValue };

/* ------------------------------------------------------------------ */
/* Enums                                                               */
/* ------------------------------------------------------------------ */

export const userRoleEnum = pgEnum("user_role", ["user", "admin"]);
export const userStatusEnum = pgEnum("user_status", ["active", "suspended"]);
export const accountStatusEnum = pgEnum("account_status", [
	"pending",
	"active",
	"paused",
	"error",
	"verification_required",
]);
export const targetKindEnum = pgEnum("target_kind", [
	"hashtag",
	"username",
	"location",
]);
export const jobTypeEnum = pgEnum("job_type", [
	"growth_run",
	"account_sync",
	"login_check",
]);
export const jobStatusEnum = pgEnum("job_status", [
	"queued",
	"running",
	"succeeded",
	"failed",
	"canceled",
]);
export const activityActionEnum = pgEnum("activity_action", [
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
export const workerStatusEnum = pgEnum("worker_status", [
	"online",
	"idle",
	"busy",
	"offline",
]);

/* ------------------------------------------------------------------ */
/* Tables                                                              */
/* ------------------------------------------------------------------ */

/**
 * Mirror of Supabase `auth.users`. The `id` matches `auth.users.id`; the
 * foreign key and the signup trigger that populates this table are created by
 * `supabase/policies.sql`.
 */
export const profiles = pgTable(
	"profiles",
	{
		id: uuid("id").primaryKey(),
		email: text("email").notNull(),
		displayName: text("display_name"),
		role: userRoleEnum("role").notNull().default("user"),
		status: userStatusEnum("status").notNull().default("active"),
		createdAt: timestamp("created_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
		updatedAt: timestamp("updated_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
		lastSeenAt: timestamp("last_seen_at", { withTimezone: true }),
	},
	(table) => [uniqueIndex("profiles_email_key").on(table.email)],
);

export const instagramAccounts = pgTable(
	"instagram_accounts",
	{
		id: uuid("id").primaryKey().defaultRandom(),
		userId: uuid("user_id")
			.notNull()
			.references(() => profiles.id, { onDelete: "cascade" }),
		username: text("username").notNull(),
		/** AES-256-GCM encrypted password payload. Never logged or returned. */
		credentials: text("credentials").notNull(),
		proxyUrl: text("proxy_url"),
		status: accountStatusEnum("status").notNull().default("pending"),
		followers: integer("followers").notNull().default(0),
		following: integer("following").notNull().default(0),
		posts: integer("posts").notNull().default(0),
		lastLoginAt: timestamp("last_login_at", { withTimezone: true }),
		lastRunAt: timestamp("last_run_at", { withTimezone: true }),
		lastError: text("last_error"),
		createdAt: timestamp("created_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
		updatedAt: timestamp("updated_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
	},
	(table) => [
		uniqueIndex("instagram_accounts_user_username_key").on(
			table.userId,
			table.username,
		),
		index("instagram_accounts_user_idx").on(table.userId),
	],
);

export const growthSettings = pgTable(
	"growth_settings",
	{
		id: uuid("id").primaryKey().defaultRandom(),
		accountId: uuid("account_id")
			.notNull()
			.references(() => instagramAccounts.id, { onDelete: "cascade" })
			.unique(),
		enabled: boolean("enabled").notNull().default(false),

		// Which activities are allowed
		likeByTags: boolean("like_by_tags").notNull().default(true),
		followByTags: boolean("follow_by_tags").notNull().default(false),
		interactByUsers: boolean("interact_by_users").notNull().default(false),
		unfollowEnabled: boolean("unfollow_enabled").notNull().default(false),
		watchStories: boolean("watch_stories").notNull().default(false),

		// Daily budget
		runsPerDay: integer("runs_per_day").notNull().default(4),
		likesPerDay: integer("likes_per_day").notNull().default(100),
		followsPerDay: integer("follows_per_day").notNull().default(40),
		unfollowsPerDay: integer("unfollows_per_day").notNull().default(40),
		commentsPerDay: integer("comments_per_day").notNull().default(15),
		storiesPerDay: integer("stories_per_day").notNull().default(20),

		// Per-run behaviour
		interactionsPerRun: integer("interactions_per_run").notNull().default(30),
		followPercentage: integer("follow_percentage").notNull().default(30),
		commentPercentage: integer("comment_percentage").notNull().default(10),
		comments: jsonb("comments").$type<string[]>().notNull().default([]),

		// Filters
		blacklistTags: jsonb("blacklist_tags")
			.$type<string[]>()
			.notNull()
			.default([]),
		ignoreUsers: jsonb("ignore_users").$type<string[]>().notNull().default([]),
		dontIncludeUsers: jsonb("dont_include_users")
			.$type<string[]>()
			.notNull()
			.default([]),
		interactUsers: jsonb("interact_users")
			.$type<string[]>()
			.notNull()
			.default([]),
		minFollowers: integer("min_followers"),
		maxFollowers: integer("max_followers"),
		minFollowing: integer("min_following"),
		maxFollowing: integer("max_following"),
		maxPostAgeDays: integer("max_post_age_days"),
		skipPrivateAccounts: boolean("skip_private_accounts")
			.notNull()
			.default(true),

		// Pacing & schedule
		actionDelayMinSec: integer("action_delay_min_sec").notNull().default(25),
		actionDelayMaxSec: integer("action_delay_max_sec").notNull().default(60),
		workingHoursStart: integer("working_hours_start").notNull().default(8),
		workingHoursEnd: integer("working_hours_end").notNull().default(23),
		daysOfWeek: jsonb("days_of_week")
			.$type<number[]>()
			.notNull()
			.default([0, 1, 2, 3, 4, 5, 6]),
		timezone: text("timezone").notNull().default("UTC"),

		createdAt: timestamp("created_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
		updatedAt: timestamp("updated_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
	},
	(table) => [index("growth_settings_account_idx").on(table.accountId)],
);

export const targets = pgTable(
	"targets",
	{
		id: uuid("id").primaryKey().defaultRandom(),
		accountId: uuid("account_id")
			.notNull()
			.references(() => instagramAccounts.id, { onDelete: "cascade" }),
		kind: targetKindEnum("kind").notNull(),
		value: text("value").notNull(),
		enabled: boolean("enabled").notNull().default(true),
		weight: integer("weight").notNull().default(1),
		createdAt: timestamp("created_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
	},
	(table) => [
		uniqueIndex("targets_account_kind_value_key").on(
			table.accountId,
			table.kind,
			table.value,
		),
		index("targets_account_idx").on(table.accountId),
	],
);

export const jobs = pgTable(
	"jobs",
	{
		id: uuid("id").primaryKey().defaultRandom(),
		userId: uuid("user_id")
			.notNull()
			.references(() => profiles.id, { onDelete: "cascade" }),
		accountId: uuid("account_id")
			.notNull()
			.references(() => instagramAccounts.id, { onDelete: "cascade" }),
		type: jobTypeEnum("type").notNull().default("growth_run"),
		status: jobStatusEnum("status").notNull().default("queued"),
		priority: integer("priority").notNull().default(0),
		/** Frozen snapshot of settings + targets at enqueue time. */
		payload: jsonb("payload").$type<JsonObject>().notNull().default({}),
		attempts: integer("attempts").notNull().default(0),
		maxAttempts: integer("max_attempts").notNull().default(2),
		progress: integer("progress").notNull().default(0),
		scheduledFor: timestamp("scheduled_for", { withTimezone: true })
			.notNull()
			.defaultNow(),
		lockedAt: timestamp("locked_at", { withTimezone: true }),
		lockedBy: text("locked_by"),
		startedAt: timestamp("started_at", { withTimezone: true }),
		finishedAt: timestamp("finished_at", { withTimezone: true }),
		result: jsonb("result").$type<JsonObject>(),
		error: text("error"),
		createdAt: timestamp("created_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
		updatedAt: timestamp("updated_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
	},
	(table) => [
		index("jobs_status_scheduled_idx").on(table.status, table.scheduledFor),
		index("jobs_account_idx").on(table.accountId),
		index("jobs_user_idx").on(table.userId),
	],
);

export const activityLogs = pgTable(
	"activity_logs",
	{
		id: uuid("id").primaryKey().defaultRandom(),
		userId: uuid("user_id")
			.notNull()
			.references(() => profiles.id, { onDelete: "cascade" }),
		accountId: uuid("account_id")
			.notNull()
			.references(() => instagramAccounts.id, { onDelete: "cascade" }),
		jobId: uuid("job_id").references(() => jobs.id, { onDelete: "set null" }),
		action: activityActionEnum("action").notNull(),
		target: text("target"),
		message: text("message"),
		detail: jsonb("detail").$type<JsonObject>(),
		createdAt: timestamp("created_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
	},
	(table) => [
		index("activity_logs_account_created_idx").on(
			table.accountId,
			table.createdAt,
		),
		index("activity_logs_user_created_idx").on(table.userId, table.createdAt),
	],
);

export const accountStatsDaily = pgTable(
	"account_stats_daily",
	{
		id: uuid("id").primaryKey().defaultRandom(),
		userId: uuid("user_id")
			.notNull()
			.references(() => profiles.id, { onDelete: "cascade" }),
		accountId: uuid("account_id")
			.notNull()
			.references(() => instagramAccounts.id, { onDelete: "cascade" }),
		day: date("day").notNull(),
		likes: integer("likes").notNull().default(0),
		follows: integer("follows").notNull().default(0),
		unfollows: integer("unfollows").notNull().default(0),
		comments: integer("comments").notNull().default(0),
		stories: integer("stories").notNull().default(0),
		errors: integer("errors").notNull().default(0),
		followers: integer("followers"),
		following: integer("following"),
		posts: integer("posts"),
		createdAt: timestamp("created_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
		updatedAt: timestamp("updated_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
	},
	(table) => [
		uniqueIndex("account_stats_daily_account_day_key").on(
			table.accountId,
			table.day,
		),
		index("account_stats_daily_user_idx").on(table.userId),
	],
);

/** Singleton row (id = 'global') with platform-wide switches. */
export const serviceSettings = pgTable("service_settings", {
	id: text("id").primaryKey().default("global"),
	workerEnabled: boolean("worker_enabled").notNull().default(true),
	maintenanceMode: boolean("maintenance_mode").notNull().default(false),
	registrationOpen: boolean("registration_open").notNull().default(true),
	maxAccountsPerUser: integer("max_accounts_per_user").notNull().default(3),
	defaultLikesPerDay: integer("default_likes_per_day").notNull().default(100),
	defaultFollowsPerDay: integer("default_follows_per_day")
		.notNull()
		.default(40),
	defaultUnfollowsPerDay: integer("default_unfollows_per_day")
		.notNull()
		.default(40),
	defaultCommentsPerDay: integer("default_comments_per_day")
		.notNull()
		.default(15),
	updatedAt: timestamp("updated_at", { withTimezone: true })
		.notNull()
		.defaultNow(),
});

/** Heartbeats from the Python automation workers. */
export const workers = pgTable(
	"workers",
	{
		id: uuid("id").primaryKey().defaultRandom(),
		name: text("name").notNull(),
		status: workerStatusEnum("status").notNull().default("online"),
		version: text("version"),
		concurrency: integer("concurrency").notNull().default(1),
		currentJobId: uuid("current_job_id"),
		lastHeartbeatAt: timestamp("last_heartbeat_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
		startedAt: timestamp("started_at", { withTimezone: true })
			.notNull()
			.defaultNow(),
	},
	(table) => [uniqueIndex("workers_name_key").on(table.name)],
);

/* ------------------------------------------------------------------ */
/* Inferred types                                                      */
/* ------------------------------------------------------------------ */

export type Profile = typeof profiles.$inferSelect;
export type InstagramAccount = typeof instagramAccounts.$inferSelect;
export type GrowthSettings = typeof growthSettings.$inferSelect;
export type Target = typeof targets.$inferSelect;
export type Job = typeof jobs.$inferSelect;
export type ActivityLog = typeof activityLogs.$inferSelect;
export type AccountStatsDaily = typeof accountStatsDaily.$inferSelect;
export type ServiceSettings = typeof serviceSettings.$inferSelect;
export type Worker = typeof workers.$inferSelect;
