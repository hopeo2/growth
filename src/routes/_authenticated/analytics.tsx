import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { AccountPicker } from "@/components/account-picker";
import { BarBreakdown, type SeriesDef, TrendChart } from "@/components/charts";
import {
	Badge,
	Card,
	CardBody,
	CardHeader,
	EmptyState,
	PageHeader,
	StatCard,
} from "@/components/ui";
import { getAnalyticsFn } from "@/functions/analytics.functions";
import { formatDay, formatNumber, statusLabel } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/analytics")({
	validateSearch: (
		search: Record<string, unknown>,
	): { account?: string; days?: number } => ({
		account: typeof search.account === "string" ? search.account : undefined,
		days: typeof search.days === "number" ? search.days : 30,
	}),
	loaderDeps: ({ search }) => ({ account: search.account, days: search.days }),
	loader: ({ deps }) =>
		getAnalyticsFn({
			data: { accountId: deps.account, days: deps.days },
		}),
	component: AnalyticsPage,
});

const SERIES: SeriesDef[] = [
	{ key: "likes", label: "Likes", color: "#ec4899" },
	{ key: "follows", label: "Follows", color: "#4f46e5" },
	{ key: "unfollows", label: "Unfollows", color: "#f59e0b" },
	{ key: "comments", label: "Comments", color: "#0ea5e9" },
];

const ACTION_COLORS: Record<string, string> = {
	like: "#ec4899",
	follow: "#4f46e5",
	unfollow: "#f59e0b",
	comment: "#0ea5e9",
	story: "#8b5cf6",
	error: "#ef4444",
};

const RANGE_OPTIONS = [7, 30, 90];

function AnalyticsPage() {
	const data = Route.useLoaderData();
	const navigate = useNavigate();

	const points = data.series.map((day) => ({
		label: formatDay(day.day),
		likes: day.likes,
		follows: day.follows,
		unfollows: day.unfollows,
		comments: day.comments,
	}));

	const breakdown = data.breakdown.map((entry) => ({
		label: statusLabel(entry.action),
		value: entry.total,
		color: ACTION_COLORS[entry.action] ?? "#71717a",
	}));

	return (
		<div className="space-y-6">
			<PageHeader
				title="Analytics"
				description="Growth trends and action breakdown across accounts."
				action={
					<div className="flex flex-wrap items-center gap-3">
						<div className="flex overflow-hidden rounded-lg border border-zinc-300">
							{RANGE_OPTIONS.map((days) => (
								<button
									key={days}
									type="button"
									onClick={() =>
										navigate({
											to: "/analytics",
											search: { account: data.accountId ?? undefined, days },
										})
									}
									className={
										data.series.length === days
											? "bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white"
											: "px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50"
									}
								>
									{days}d
								</button>
							))}
						</div>
						<AccountPicker
							accounts={data.accounts}
							value={data.accountId ?? undefined}
							onChange={(account) =>
								navigate({
									to: "/analytics",
									search: { account, days: data.series.length },
								})
							}
						/>
					</div>
				}
			/>

			<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<StatCard
					label="Interactions"
					value={formatNumber(data.totals.interactions)}
					icon="⚡"
					tone="indigo"
				/>
				<StatCard
					label="Likes"
					value={formatNumber(data.totals.likes)}
					icon="❤️"
					tone="emerald"
				/>
				<StatCard
					label="Follows"
					value={formatNumber(data.totals.follows)}
					icon="➕"
				/>
				<StatCard
					label="Errors"
					value={formatNumber(data.totals.errors)}
					icon="⚠️"
					tone="red"
				/>
			</div>

			<Card>
				<CardHeader title={`Interactions — last ${data.series.length} days`} />
				<CardBody>
					{data.totals.interactions === 0 ? (
						<EmptyState
							title="No interactions in this range"
							description="Enable growth automation and run a job to see data here."
						/>
					) : (
						<TrendChart data={points} series={SERIES} height={280} />
					)}
				</CardBody>
			</Card>

			<div className="grid gap-6 lg:grid-cols-3">
				<Card className="lg:col-span-2">
					<CardHeader title="Daily breakdown" />
					{data.series.length === 0 ? (
						<EmptyState title="Nothing to show" />
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-sm">
								<thead>
									<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
										<th className="px-5 py-3 font-medium">Day</th>
										<th className="px-5 py-3 font-medium">Likes</th>
										<th className="px-5 py-3 font-medium">Follows</th>
										<th className="px-5 py-3 font-medium">Unfollows</th>
										<th className="px-5 py-3 font-medium">Comments</th>
										<th className="px-5 py-3 font-medium">Errors</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-zinc-100">
									{[...data.series].reverse().map((day) => (
										<tr key={day.day}>
											<td className="px-5 py-2.5 font-medium text-zinc-700">
												{day.day}
											</td>
											<td className="px-5 py-2.5 text-zinc-600">{day.likes}</td>
											<td className="px-5 py-2.5 text-zinc-600">
												{day.follows}
											</td>
											<td className="px-5 py-2.5 text-zinc-600">
												{day.unfollows}
											</td>
											<td className="px-5 py-2.5 text-zinc-600">
												{day.comments}
											</td>
											<td className="px-5 py-2.5 text-zinc-600">
												{day.errors}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</Card>

				<div className="space-y-6">
					<Card>
						<CardHeader title="Actions by type" />
						<CardBody>
							<BarBreakdown data={breakdown} />
						</CardBody>
					</Card>

					{data.targetCounts ? (
						<Card>
							<CardHeader title="Active targets" />
							<CardBody className="flex flex-wrap gap-2">
								<Badge variant="follow">
									{data.targetCounts.hashtags} hashtags
								</Badge>
								<Badge variant="comment">{data.targetCounts.users} users</Badge>
								<Badge variant="story">
									{data.targetCounts.locations} locations
								</Badge>
							</CardBody>
						</Card>
					) : null}
				</div>
			</div>
		</div>
	);
}
