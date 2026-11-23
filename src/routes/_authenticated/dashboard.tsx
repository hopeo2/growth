import { createFileRoute, Link } from "@tanstack/react-router";

import { type SeriesDef, TrendChart } from "@/components/charts";
import {
	Badge,
	Card,
	CardBody,
	CardHeader,
	EmptyState,
	PageHeader,
	Spinner,
	StatCard,
} from "@/components/ui";
import { getDashboardFn } from "@/functions/analytics.functions";
import {
	formatDateTime,
	formatNumber,
	relativeTime,
	statusLabel,
} from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/dashboard")({
	loader: () => getDashboardFn(),
	component: DashboardPage,
});

const SERIES: SeriesDef[] = [
	{ key: "likes", label: "Likes", color: "#ec4899" },
	{ key: "follows", label: "Follows", color: "#4f46e5" },
	{ key: "comments", label: "Comments", color: "#0ea5e9" },
];

const ACTION_VARIANT: Record<string, string> = {
	like: "like",
	follow: "follow",
	unfollow: "unfollow",
	comment: "comment",
	story: "story",
	login: "login",
	info: "info",
	warning: "warning",
	error: "error",
};

function DashboardPage() {
	const data = Route.useLoaderData();
	const points = data.series.map((day) => ({
		label: day.day.slice(5),
		likes: day.likes,
		follows: day.follows,
		comments: day.comments,
	}));
	const activeAccounts = data.accounts.filter(
		(account) => account.status === "active",
	).length;

	return (
		<div className="space-y-6">
			<PageHeader
				title="Dashboard"
				description="Growth, activity and account status at a glance."
				action={
					<Link
						to="/accounts"
						className="rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-500"
					>
						Add account
					</Link>
				}
			/>

			<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<StatCard
					label="Accounts"
					value={data.accounts.length}
					hint={`${activeAccounts} active`}
					icon="👤"
					tone="indigo"
				/>
				<StatCard
					label="Interactions today"
					value={formatNumber(data.totals.today.interactions)}
					hint={`${formatNumber(data.totals.today.errors)} errors`}
					icon="⚡"
					tone="emerald"
				/>
				<StatCard
					label="Interactions (7 days)"
					value={formatNumber(data.totals.last7.interactions)}
					hint={`${formatNumber(data.totals.last30.interactions)} in 30 days`}
					icon="📈"
				/>
				<StatCard
					label="Followers"
					value={formatNumber(data.followerTotal)}
					hint={`${formatNumber(data.followingTotal)} following`}
					icon="❤️"
					tone="amber"
				/>
			</div>

			<div className="grid gap-6 lg:grid-cols-3">
				<Card className="lg:col-span-2">
					<CardHeader
						title="Interactions — last 14 days"
						description="Likes, follows and comments performed by the workers."
					/>
					<CardBody>
						{data.series.every(
							(day) => day.likes + day.follows + day.comments === 0,
						) ? (
							<EmptyState
								title="No activity yet"
								description="Once a worker runs a growth job, the daily numbers will appear here."
							/>
						) : (
							<TrendChart data={points} series={SERIES} />
						)}
					</CardBody>
				</Card>

				<div className="space-y-6">
					<Card>
						<CardHeader title="Active jobs" />
						<CardBody className="space-y-3">
							{data.activeJobs.length === 0 ? (
								<p className="text-sm text-zinc-500">
									No queued or running jobs.
								</p>
							) : (
								data.activeJobs.slice(0, 5).map((job) => (
									<div
										key={job.id}
										className="flex items-center justify-between gap-3 text-sm"
									>
										<div className="min-w-0">
											<p className="truncate font-medium text-zinc-800">
												{job.type.replace("_", " ")}
											</p>
											<p className="text-xs text-zinc-500">
												{relativeTime(job.createdAt)}
											</p>
										</div>
										<div className="flex items-center gap-2">
											{job.status === "running" ? (
												<Spinner className="size-3.5" />
											) : null}
											<Badge variant={job.status}>
												{statusLabel(job.status)}
											</Badge>
										</div>
									</div>
								))
							)}
						</CardBody>
					</Card>

					<Card>
						<CardHeader title="Accounts" />
						<CardBody className="space-y-3">
							{data.accounts.length === 0 ? (
								<p className="text-sm text-zinc-500">
									No accounts connected yet.
								</p>
							) : (
								data.accounts.slice(0, 5).map((account) => (
									<Link
										key={account.id}
										to="/accounts/$accountId"
										params={{ accountId: account.id }}
										className="flex items-center justify-between gap-3 rounded-lg px-1 py-1 text-sm hover:bg-zinc-50"
									>
										<span className="min-w-0">
											<span className="block truncate font-medium text-zinc-800">
												@{account.username}
											</span>
											<span className="text-xs text-zinc-500">
												{formatNumber(account.followers)} followers
											</span>
										</span>
										<Badge variant={account.status}>
											{statusLabel(account.status)}
										</Badge>
									</Link>
								))
							)}
						</CardBody>
					</Card>
				</div>
			</div>

			<Card>
				<CardHeader
					title="Recent activity"
					action={
						<Link
							to="/logs"
							className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
						>
							View all
						</Link>
					}
				/>
				<CardBody>
					{data.recentLogs.length === 0 ? (
						<EmptyState
							title="Nothing logged yet"
							description="Worker actions will stream in here as they happen."
						/>
					) : (
						<ul className="divide-y divide-zinc-100">
							{data.recentLogs.map((log) => (
								<li
									key={log.id}
									className="flex items-center justify-between gap-4 py-2.5 text-sm"
								>
									<div className="flex min-w-0 items-center gap-3">
										<Badge variant={ACTION_VARIANT[log.action] ?? "default"}>
											{log.action}
										</Badge>
										<span className="truncate text-zinc-600">
											{log.message ?? log.target ?? "—"}
										</span>
									</div>
									<span className="shrink-0 text-xs text-zinc-400">
										{formatDateTime(log.createdAt)}
									</span>
								</li>
							))}
						</ul>
					)}
				</CardBody>
			</Card>
		</div>
	);
}
