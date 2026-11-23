import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { type FormEvent, useState } from "react";

import { AccountPicker } from "@/components/account-picker";
import {
	Alert,
	Button,
	Card,
	CardBody,
	CardHeader,
	Checkbox,
	EmptyState,
	Field,
	Input,
	PageHeader,
} from "@/components/ui";
import type { GrowthSettings } from "@/db";
import { listAccountsFn } from "@/functions/accounts.functions";
import {
	getGrowthSettingsFn,
	saveGrowthSettingsFn,
} from "@/functions/settings.functions";
import { useMutationAction } from "@/lib/use-mutation";
import { formatDateTime } from "@/lib/utils";
import type { AccountSummary } from "@/server/accounts.server";

export const Route = createFileRoute("/_authenticated/settings")({
	validateSearch: (search: Record<string, unknown>): { account?: string } => ({
		account: typeof search.account === "string" ? search.account : undefined,
	}),
	loaderDeps: ({ search }) => ({ account: search.account }),
	loader: async ({ deps }) => {
		const accounts = await listAccountsFn();
		const accountId =
			deps.account && accounts.some((account) => account.id === deps.account)
				? deps.account
				: accounts[0]?.id;
		const settings = accountId
			? await getGrowthSettingsFn({ data: { accountId } })
			: null;
		return { accounts, accountId, settings };
	},
	component: SettingsPage,
});

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

type FormState = {
	enabled: boolean;
	likeByTags: boolean;
	followByTags: boolean;
	interactByUsers: boolean;
	unfollowEnabled: boolean;
	watchStories: boolean;
	runsPerDay: number;
	likesPerDay: number;
	followsPerDay: number;
	unfollowsPerDay: number;
	commentsPerDay: number;
	storiesPerDay: number;
	interactionsPerRun: number;
	followPercentage: number;
	commentPercentage: number;
	comments: string;
	blacklistTags: string;
	ignoreUsers: string;
	dontIncludeUsers: string;
	interactUsers: string;
	minFollowers: string;
	maxFollowers: string;
	minFollowing: string;
	maxFollowing: string;
	maxPostAgeDays: string;
	skipPrivateAccounts: boolean;
	actionDelayMinSec: number;
	actionDelayMaxSec: number;
	workingHoursStart: number;
	workingHoursEnd: number;
	daysOfWeek: number[];
	timezone: string;
};

function toLines(values: string[]): string {
	return values.join("\n");
}

function fromLines(value: string): string[] {
	return value
		.split(/[\n,]/)
		.map((entry) => entry.trim())
		.filter(Boolean);
}

function buildForm(settings: GrowthSettings): FormState {
	return {
		enabled: settings.enabled,
		likeByTags: settings.likeByTags,
		followByTags: settings.followByTags,
		interactByUsers: settings.interactByUsers,
		unfollowEnabled: settings.unfollowEnabled,
		watchStories: settings.watchStories,
		runsPerDay: settings.runsPerDay,
		likesPerDay: settings.likesPerDay,
		followsPerDay: settings.followsPerDay,
		unfollowsPerDay: settings.unfollowsPerDay,
		commentsPerDay: settings.commentsPerDay,
		storiesPerDay: settings.storiesPerDay,
		interactionsPerRun: settings.interactionsPerRun,
		followPercentage: settings.followPercentage,
		commentPercentage: settings.commentPercentage,
		comments: toLines(settings.comments),
		blacklistTags: toLines(settings.blacklistTags),
		ignoreUsers: toLines(settings.ignoreUsers),
		dontIncludeUsers: toLines(settings.dontIncludeUsers),
		interactUsers: toLines(settings.interactUsers),
		minFollowers: settings.minFollowers?.toString() ?? "",
		maxFollowers: settings.maxFollowers?.toString() ?? "",
		minFollowing: settings.minFollowing?.toString() ?? "",
		maxFollowing: settings.maxFollowing?.toString() ?? "",
		maxPostAgeDays: settings.maxPostAgeDays?.toString() ?? "",
		skipPrivateAccounts: settings.skipPrivateAccounts,
		actionDelayMinSec: settings.actionDelayMinSec,
		actionDelayMaxSec: settings.actionDelayMaxSec,
		workingHoursStart: settings.workingHoursStart,
		workingHoursEnd: settings.workingHoursEnd,
		daysOfWeek: settings.daysOfWeek,
		timezone: settings.timezone,
	};
}

function numberOrNull(value: string): number | null {
	const trimmed = value.trim();
	if (trimmed === "") return null;
	const parsed = Number(trimmed);
	return Number.isFinite(parsed) ? Math.trunc(parsed) : null;
}

const TEXTAREA_CLASS =
	"min-h-20 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100";

function NumberField({
	label,
	value,
	onChange,
	hint,
	min = 0,
	max,
}: {
	label: string;
	value: number;
	onChange: (value: number) => void;
	hint?: string;
	min?: number;
	max?: number;
}) {
	return (
		<Field label={label} hint={hint}>
			<Input
				type="number"
				min={min}
				max={max}
				value={value}
				onChange={(event) => onChange(Number(event.target.value))}
			/>
		</Field>
	);
}

function SettingsPage() {
	const { accounts, accountId, settings } = Route.useLoaderData();
	const navigate = useNavigate();

	if (!accountId || !settings) {
		return (
			<div className="space-y-6">
				<PageHeader title="Growth settings" />
				<Card>
					<EmptyState
						title="Add an account first"
						description="Growth settings are configured per Instagram account."
					/>
				</Card>
			</div>
		);
	}

	return (
		<SettingsForm
			key={accountId}
			accounts={accounts}
			accountId={accountId}
			settings={settings}
			onAccountChange={(next) =>
				navigate({ to: "/settings", search: { account: next } })
			}
		/>
	);
}

function SettingsForm({
	accounts,
	accountId,
	settings,
	onAccountChange,
}: {
	accounts: AccountSummary[];
	accountId: string;
	settings: GrowthSettings;
	onAccountChange: (accountId: string) => void;
}) {
	const saveSettings = useServerFn(saveGrowthSettingsFn);
	const { pending, error, setError, run } = useMutationAction();
	const [saved, setSaved] = useState(false);
	const [form, setForm] = useState<FormState>(() => buildForm(settings));

	const patch = (values: Partial<FormState>) =>
		setForm((current) => ({ ...current, ...values }));

	async function handleSubmit(event: FormEvent) {
		event.preventDefault();
		setSaved(false);

		if (form.actionDelayMaxSec < form.actionDelayMinSec) {
			setError(
				"Maximum delay must be greater than or equal to the minimum delay",
			);
			return;
		}
		if (form.daysOfWeek.length === 0) {
			setError("Select at least one day of the week");
			return;
		}

		const ok = await run(() =>
			saveSettings({
				data: {
					accountId,
					enabled: form.enabled,
					likeByTags: form.likeByTags,
					followByTags: form.followByTags,
					interactByUsers: form.interactByUsers,
					unfollowEnabled: form.unfollowEnabled,
					watchStories: form.watchStories,
					runsPerDay: form.runsPerDay,
					likesPerDay: form.likesPerDay,
					followsPerDay: form.followsPerDay,
					unfollowsPerDay: form.unfollowsPerDay,
					commentsPerDay: form.commentsPerDay,
					storiesPerDay: form.storiesPerDay,
					interactionsPerRun: form.interactionsPerRun,
					followPercentage: form.followPercentage,
					commentPercentage: form.commentPercentage,
					comments: fromLines(form.comments),
					blacklistTags: fromLines(form.blacklistTags),
					ignoreUsers: fromLines(form.ignoreUsers),
					dontIncludeUsers: fromLines(form.dontIncludeUsers),
					interactUsers: fromLines(form.interactUsers),
					minFollowers: numberOrNull(form.minFollowers),
					maxFollowers: numberOrNull(form.maxFollowers),
					minFollowing: numberOrNull(form.minFollowing),
					maxFollowing: numberOrNull(form.maxFollowing),
					maxPostAgeDays: numberOrNull(form.maxPostAgeDays),
					skipPrivateAccounts: form.skipPrivateAccounts,
					actionDelayMinSec: form.actionDelayMinSec,
					actionDelayMaxSec: form.actionDelayMaxSec,
					workingHoursStart: form.workingHoursStart,
					workingHoursEnd: form.workingHoursEnd,
					daysOfWeek: form.daysOfWeek,
					timezone: form.timezone,
				},
			}),
		);
		setSaved(ok);
	}

	const username =
		accounts.find((account) => account.id === accountId)?.username ?? "";

	return (
		<form onSubmit={handleSubmit} className="space-y-6">
			<PageHeader
				title="Growth settings"
				description={`Automation behaviour for @${username}`}
				action={
					<div className="flex items-center gap-3">
						<AccountPicker
							accounts={accounts}
							value={accountId}
							onChange={onAccountChange}
						/>
						<Button type="submit" loading={pending}>
							Save settings
						</Button>
					</div>
				}
			/>

			{error ? <Alert>{error}</Alert> : null}
			{saved ? <Alert tone="success">Settings saved.</Alert> : null}

			<Card>
				<CardHeader
					title="General"
					description="Master switch and the automated activities to perform."
				/>
				<CardBody className="space-y-4">
					<Checkbox
						label="Enable growth automation for this account"
						checked={form.enabled}
						onChange={(event) => patch({ enabled: event.target.checked })}
					/>
					<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
						<Checkbox
							label="Like posts by hashtags"
							checked={form.likeByTags}
							onChange={(event) => patch({ likeByTags: event.target.checked })}
						/>
						<Checkbox
							label="Follow users from hashtags"
							checked={form.followByTags}
							onChange={(event) =>
								patch({ followByTags: event.target.checked })
							}
						/>
						<Checkbox
							label="Interact with specific users"
							checked={form.interactByUsers}
							onChange={(event) =>
								patch({ interactByUsers: event.target.checked })
							}
						/>
						<Checkbox
							label="Unfollow non-followers"
							checked={form.unfollowEnabled}
							onChange={(event) =>
								patch({ unfollowEnabled: event.target.checked })
							}
						/>
						<Checkbox
							label="Watch stories"
							checked={form.watchStories}
							onChange={(event) =>
								patch({ watchStories: event.target.checked })
							}
						/>
						<Checkbox
							label="Skip private accounts"
							checked={form.skipPrivateAccounts}
							onChange={(event) =>
								patch({ skipPrivateAccounts: event.target.checked })
							}
						/>
					</div>
				</CardBody>
			</Card>

			<Card>
				<CardHeader
					title="Daily budget"
					description="Maximum actions spread across the day by the scheduler."
				/>
				<CardBody className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
					<NumberField
						label="Runs per day"
						value={form.runsPerDay}
						max={96}
						onChange={(value) => patch({ runsPerDay: value })}
					/>
					<NumberField
						label="Likes / day"
						value={form.likesPerDay}
						max={2000}
						onChange={(value) => patch({ likesPerDay: value })}
					/>
					<NumberField
						label="Follows / day"
						value={form.followsPerDay}
						max={1000}
						onChange={(value) => patch({ followsPerDay: value })}
					/>
					<NumberField
						label="Unfollows / day"
						value={form.unfollowsPerDay}
						max={1000}
						onChange={(value) => patch({ unfollowsPerDay: value })}
					/>
					<NumberField
						label="Comments / day"
						value={form.commentsPerDay}
						max={500}
						onChange={(value) => patch({ commentsPerDay: value })}
					/>
					<NumberField
						label="Stories / day"
						value={form.storiesPerDay}
						max={500}
						onChange={(value) => patch({ storiesPerDay: value })}
					/>
				</CardBody>
			</Card>

			<Card>
				<CardHeader title="Per-run behaviour" />
				<CardBody className="grid gap-4 sm:grid-cols-3">
					<NumberField
						label="Interactions per run"
						value={form.interactionsPerRun}
						min={1}
						max={500}
						onChange={(value) => patch({ interactionsPerRun: value })}
					/>
					<NumberField
						label="Follow percentage"
						hint="% of visited posts to follow"
						value={form.followPercentage}
						max={100}
						onChange={(value) => patch({ followPercentage: value })}
					/>
					<NumberField
						label="Comment percentage"
						hint="% of visited posts to comment"
						value={form.commentPercentage}
						max={100}
						onChange={(value) => patch({ commentPercentage: value })}
					/>
					<Field
						label="Comment templates"
						hint="One per line. InstaPy picks randomly."
						className="sm:col-span-3"
					>
						<textarea
							className={TEXTAREA_CLASS}
							value={form.comments}
							onChange={(event) => patch({ comments: event.target.value })}
						/>
					</Field>
				</CardBody>
			</Card>

			<Card>
				<CardHeader
					title="Filters"
					description="Audience quality and safety filters."
				/>
				<CardBody className="grid gap-4 sm:grid-cols-3">
					<Field label="Min followers" hint="Leave empty for no limit">
						<Input
							type="number"
							value={form.minFollowers}
							onChange={(event) => patch({ minFollowers: event.target.value })}
						/>
					</Field>
					<Field label="Max followers">
						<Input
							type="number"
							value={form.maxFollowers}
							onChange={(event) => patch({ maxFollowers: event.target.value })}
						/>
					</Field>
					<Field label="Min following">
						<Input
							type="number"
							value={form.minFollowing}
							onChange={(event) => patch({ minFollowing: event.target.value })}
						/>
					</Field>
					<Field label="Max following">
						<Input
							type="number"
							value={form.maxFollowing}
							onChange={(event) => patch({ maxFollowing: event.target.value })}
						/>
					</Field>
					<Field label="Max post age (days)">
						<Input
							type="number"
							value={form.maxPostAgeDays}
							onChange={(event) =>
								patch({ maxPostAgeDays: event.target.value })
							}
						/>
					</Field>
					<Field label="Blacklisted tags" hint="One per line, never liked">
						<textarea
							className={TEXTAREA_CLASS}
							value={form.blacklistTags}
							onChange={(event) => patch({ blacklistTags: event.target.value })}
						/>
					</Field>
					<Field label="Ignored users" hint="One per line">
						<textarea
							className={TEXTAREA_CLASS}
							value={form.ignoreUsers}
							onChange={(event) => patch({ ignoreUsers: event.target.value })}
						/>
					</Field>
					<Field label="Never include" hint="Friends to never interact with">
						<textarea
							className={TEXTAREA_CLASS}
							value={form.dontIncludeUsers}
							onChange={(event) =>
								patch({ dontIncludeUsers: event.target.value })
							}
						/>
					</Field>
					<Field
						label="Interact-with users"
						hint="Used by the 'interact by users' activity"
					>
						<textarea
							className={TEXTAREA_CLASS}
							value={form.interactUsers}
							onChange={(event) => patch({ interactUsers: event.target.value })}
						/>
					</Field>
				</CardBody>
			</Card>

			<Card>
				<CardHeader
					title="Schedule & pacing"
					description="When the worker may run and how fast."
				/>
				<CardBody className="space-y-4">
					<div className="grid gap-4 sm:grid-cols-4">
						<NumberField
							label="Start hour"
							value={form.workingHoursStart}
							max={23}
							onChange={(value) => patch({ workingHoursStart: value })}
						/>
						<NumberField
							label="End hour"
							value={form.workingHoursEnd}
							max={23}
							onChange={(value) => patch({ workingHoursEnd: value })}
						/>
						<NumberField
							label="Min delay (sec)"
							value={form.actionDelayMinSec}
							min={1}
							max={600}
							onChange={(value) => patch({ actionDelayMinSec: value })}
						/>
						<NumberField
							label="Max delay (sec)"
							value={form.actionDelayMaxSec}
							min={1}
							max={600}
							onChange={(value) => patch({ actionDelayMaxSec: value })}
						/>
					</div>
					<Field
						label="Timezone"
						hint="IANA timezone, e.g. Europe/Berlin or Asia/Tehran"
					>
						<Input
							value={form.timezone}
							onChange={(event) => patch({ timezone: event.target.value })}
						/>
					</Field>
					<div>
						<span className="mb-1.5 block text-xs font-medium text-zinc-700">
							Active days
						</span>
						<div className="flex flex-wrap gap-3">
							{WEEKDAYS.map((day, index) => (
								<Checkbox
									key={day}
									label={day}
									checked={form.daysOfWeek.includes(index)}
									onChange={(event) => {
										const next = event.target.checked
											? [...form.daysOfWeek, index]
											: form.daysOfWeek.filter((value) => value !== index);
										patch({ daysOfWeek: Array.from(new Set(next)).sort() });
									}}
								/>
							))}
						</div>
					</div>
					<p className="text-xs text-zinc-400">
						Last saved {formatDateTime(settings.updatedAt)}
					</p>
				</CardBody>
			</Card>

			<div className="flex justify-end">
				<Button type="submit" loading={pending}>
					Save settings
				</Button>
			</div>
		</form>
	);
}
