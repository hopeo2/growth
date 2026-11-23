CREATE TYPE "public"."account_status" AS ENUM('pending', 'active', 'paused', 'error', 'verification_required');--> statement-breakpoint
CREATE TYPE "public"."activity_action" AS ENUM('like', 'follow', 'unfollow', 'comment', 'story', 'login', 'info', 'warning', 'error');--> statement-breakpoint
CREATE TYPE "public"."job_status" AS ENUM('queued', 'running', 'succeeded', 'failed', 'canceled');--> statement-breakpoint
CREATE TYPE "public"."job_type" AS ENUM('growth_run', 'account_sync', 'login_check');--> statement-breakpoint
CREATE TYPE "public"."target_kind" AS ENUM('hashtag', 'username', 'location');--> statement-breakpoint
CREATE TYPE "public"."user_role" AS ENUM('user', 'admin');--> statement-breakpoint
CREATE TYPE "public"."user_status" AS ENUM('active', 'suspended');--> statement-breakpoint
CREATE TYPE "public"."worker_status" AS ENUM('online', 'idle', 'busy', 'offline');--> statement-breakpoint
CREATE TABLE "account_stats_daily" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"account_id" uuid NOT NULL,
	"day" date NOT NULL,
	"likes" integer DEFAULT 0 NOT NULL,
	"follows" integer DEFAULT 0 NOT NULL,
	"unfollows" integer DEFAULT 0 NOT NULL,
	"comments" integer DEFAULT 0 NOT NULL,
	"stories" integer DEFAULT 0 NOT NULL,
	"errors" integer DEFAULT 0 NOT NULL,
	"followers" integer,
	"following" integer,
	"posts" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "activity_logs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"account_id" uuid NOT NULL,
	"job_id" uuid,
	"action" "activity_action" NOT NULL,
	"target" text,
	"message" text,
	"detail" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "growth_settings" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"account_id" uuid NOT NULL,
	"enabled" boolean DEFAULT false NOT NULL,
	"like_by_tags" boolean DEFAULT true NOT NULL,
	"follow_by_tags" boolean DEFAULT false NOT NULL,
	"interact_by_users" boolean DEFAULT false NOT NULL,
	"unfollow_enabled" boolean DEFAULT false NOT NULL,
	"watch_stories" boolean DEFAULT false NOT NULL,
	"runs_per_day" integer DEFAULT 4 NOT NULL,
	"likes_per_day" integer DEFAULT 100 NOT NULL,
	"follows_per_day" integer DEFAULT 40 NOT NULL,
	"unfollows_per_day" integer DEFAULT 40 NOT NULL,
	"comments_per_day" integer DEFAULT 15 NOT NULL,
	"stories_per_day" integer DEFAULT 20 NOT NULL,
	"interactions_per_run" integer DEFAULT 30 NOT NULL,
	"follow_percentage" integer DEFAULT 30 NOT NULL,
	"comment_percentage" integer DEFAULT 10 NOT NULL,
	"comments" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"blacklist_tags" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"ignore_users" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"dont_include_users" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"interact_users" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"min_followers" integer,
	"max_followers" integer,
	"min_following" integer,
	"max_following" integer,
	"max_post_age_days" integer,
	"skip_private_accounts" boolean DEFAULT true NOT NULL,
	"action_delay_min_sec" integer DEFAULT 25 NOT NULL,
	"action_delay_max_sec" integer DEFAULT 60 NOT NULL,
	"working_hours_start" integer DEFAULT 8 NOT NULL,
	"working_hours_end" integer DEFAULT 23 NOT NULL,
	"days_of_week" jsonb DEFAULT '[0,1,2,3,4,5,6]'::jsonb NOT NULL,
	"timezone" text DEFAULT 'UTC' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "growth_settings_account_id_unique" UNIQUE("account_id")
);
--> statement-breakpoint
CREATE TABLE "instagram_accounts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"username" text NOT NULL,
	"credentials" text NOT NULL,
	"proxy_url" text,
	"status" "account_status" DEFAULT 'pending' NOT NULL,
	"followers" integer DEFAULT 0 NOT NULL,
	"following" integer DEFAULT 0 NOT NULL,
	"posts" integer DEFAULT 0 NOT NULL,
	"last_login_at" timestamp with time zone,
	"last_run_at" timestamp with time zone,
	"last_error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "jobs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"account_id" uuid NOT NULL,
	"type" "job_type" DEFAULT 'growth_run' NOT NULL,
	"status" "job_status" DEFAULT 'queued' NOT NULL,
	"priority" integer DEFAULT 0 NOT NULL,
	"payload" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"attempts" integer DEFAULT 0 NOT NULL,
	"max_attempts" integer DEFAULT 2 NOT NULL,
	"progress" integer DEFAULT 0 NOT NULL,
	"scheduled_for" timestamp with time zone DEFAULT now() NOT NULL,
	"locked_at" timestamp with time zone,
	"locked_by" text,
	"started_at" timestamp with time zone,
	"finished_at" timestamp with time zone,
	"result" jsonb,
	"error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "profiles" (
	"id" uuid PRIMARY KEY NOT NULL,
	"email" text NOT NULL,
	"display_name" text,
	"role" "user_role" DEFAULT 'user' NOT NULL,
	"status" "user_status" DEFAULT 'active' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "service_settings" (
	"id" text PRIMARY KEY DEFAULT 'global' NOT NULL,
	"worker_enabled" boolean DEFAULT true NOT NULL,
	"maintenance_mode" boolean DEFAULT false NOT NULL,
	"registration_open" boolean DEFAULT true NOT NULL,
	"max_accounts_per_user" integer DEFAULT 3 NOT NULL,
	"default_likes_per_day" integer DEFAULT 100 NOT NULL,
	"default_follows_per_day" integer DEFAULT 40 NOT NULL,
	"default_unfollows_per_day" integer DEFAULT 40 NOT NULL,
	"default_comments_per_day" integer DEFAULT 15 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "targets" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"account_id" uuid NOT NULL,
	"kind" "target_kind" NOT NULL,
	"value" text NOT NULL,
	"enabled" boolean DEFAULT true NOT NULL,
	"weight" integer DEFAULT 1 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "workers" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	"status" "worker_status" DEFAULT 'online' NOT NULL,
	"version" text,
	"concurrency" integer DEFAULT 1 NOT NULL,
	"current_job_id" uuid,
	"last_heartbeat_at" timestamp with time zone DEFAULT now() NOT NULL,
	"started_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "account_stats_daily" ADD CONSTRAINT "account_stats_daily_user_id_profiles_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "account_stats_daily" ADD CONSTRAINT "account_stats_daily_account_id_instagram_accounts_id_fk" FOREIGN KEY ("account_id") REFERENCES "public"."instagram_accounts"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "activity_logs" ADD CONSTRAINT "activity_logs_user_id_profiles_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "activity_logs" ADD CONSTRAINT "activity_logs_account_id_instagram_accounts_id_fk" FOREIGN KEY ("account_id") REFERENCES "public"."instagram_accounts"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "activity_logs" ADD CONSTRAINT "activity_logs_job_id_jobs_id_fk" FOREIGN KEY ("job_id") REFERENCES "public"."jobs"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "growth_settings" ADD CONSTRAINT "growth_settings_account_id_instagram_accounts_id_fk" FOREIGN KEY ("account_id") REFERENCES "public"."instagram_accounts"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "instagram_accounts" ADD CONSTRAINT "instagram_accounts_user_id_profiles_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_user_id_profiles_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_account_id_instagram_accounts_id_fk" FOREIGN KEY ("account_id") REFERENCES "public"."instagram_accounts"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "targets" ADD CONSTRAINT "targets_account_id_instagram_accounts_id_fk" FOREIGN KEY ("account_id") REFERENCES "public"."instagram_accounts"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "account_stats_daily_account_day_key" ON "account_stats_daily" USING btree ("account_id","day");--> statement-breakpoint
CREATE INDEX "account_stats_daily_user_idx" ON "account_stats_daily" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "activity_logs_account_created_idx" ON "activity_logs" USING btree ("account_id","created_at");--> statement-breakpoint
CREATE INDEX "activity_logs_user_created_idx" ON "activity_logs" USING btree ("user_id","created_at");--> statement-breakpoint
CREATE INDEX "growth_settings_account_idx" ON "growth_settings" USING btree ("account_id");--> statement-breakpoint
CREATE UNIQUE INDEX "instagram_accounts_user_username_key" ON "instagram_accounts" USING btree ("user_id","username");--> statement-breakpoint
CREATE INDEX "instagram_accounts_user_idx" ON "instagram_accounts" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "jobs_status_scheduled_idx" ON "jobs" USING btree ("status","scheduled_for");--> statement-breakpoint
CREATE INDEX "jobs_account_idx" ON "jobs" USING btree ("account_id");--> statement-breakpoint
CREATE INDEX "jobs_user_idx" ON "jobs" USING btree ("user_id");--> statement-breakpoint
CREATE UNIQUE INDEX "profiles_email_key" ON "profiles" USING btree ("email");--> statement-breakpoint
CREATE UNIQUE INDEX "targets_account_kind_value_key" ON "targets" USING btree ("account_id","kind","value");--> statement-breakpoint
CREATE INDEX "targets_account_idx" ON "targets" USING btree ("account_id");--> statement-breakpoint
CREATE UNIQUE INDEX "workers_name_key" ON "workers" USING btree ("name");