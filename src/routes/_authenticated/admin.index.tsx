import { createFileRoute } from "@tanstack/react-router";

import {
	Badge,
	Card,
	CardBody,
	CardHeader,
	EmptyState,
	PageHeader,
	StatCard,
} from "@/components/ui";
import { getAdminOverviewFn } from "@/functions/admin.functions";
import {
	formatDateTime,
	formatNumber,
	relativeTime,
	statusLabel,
} from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/admin/")({
	loader: () => getAdminOverviewFn(),
	component: AdminOverviewPage,
});

function AdminOverviewPage() {
	const data = Route.useLoaderData();

	return (
		<div className="space-y-6">
			<PageHeader
				title="Admin overview"
				description="Platform health, users and automation workers."
			/>

			<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<StatCard
					label="Users"
					value={data.userCount}
					hint={`${data.activeUserCount} active · ${data.suspendedUserCount} suspended`}
					icon="👥"
					tone="indigo"
				/>
				<StatCard
					label="Accounts"
					value={data.accountCount}
					hint={`${data.activeAccountCount} active · ${data.errorAccountCount} in error`}
					icon="📸"
					tone="emerald"
				/>
				<StatCard
					label="Interactions (30d)"
					value={formatNumber(data.interactions30d)}
					icon="⚡"
				/>
				<StatCard
					label="New users (7d)"
					value={data.newUsers7d}
					hint={`${data.adminCount} admins`}
					icon="🆕"
					tone="amber"
				/>
			</div>

			<div className="grid gap-6 lg:grid-cols-2">
				<Card>
					<CardHeader title="Jobs by status" />
					<CardBody className="flex flex-wrap gap-2">
						{Object.keys(data.jobCounts).length === 0 ? (
							<p className="text-sm text-zinc-500">No jobs recorded yet.</p>
						) : (
							Object.entries(data.jobCounts).map(([status, value]) => (
								<Badge key={status} variant={status}>
									{statusLabel(status)}: {value}
								</Badge>
							))
						)}
					</CardBody>
				</Card>

				<Card>
					<CardHeader
						title="Workers"
						description="Python automation workers reporting heartbeats."
					/>
					{data.workers.length === 0 ? (
						<EmptyState
							title="No workers online"
							description="Start the worker process to begin executing jobs."
						/>
					) : (
						<div className="overflow-x-auto">
							<table className="w-full text-sm">
								<thead>
									<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
										<th className="px-5 py-3 font-medium">Name</th>
										<th className="px-5 py-3 font-medium">Status</th>
										<th className="px-5 py-3 font-medium">Last seen</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-zinc-100">
									{data.workers.map((worker) => (
										<tr key={worker.id}>
											<td className="px-5 py-3 font-medium text-zinc-800">
												{worker.name}
											</td>
											<td className="px-5 py-3">
												<Badge variant={worker.status}>
													{statusLabel(worker.status)}
												</Badge>
											</td>
											<td className="px-5 py-3 text-zinc-500">
												{relativeTime(worker.lastHeartbeatAt)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}
				</Card>
			</div>

			<Card>
				<CardHeader title="Recent signups" />
				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
								<th className="px-5 py-3 font-medium">Email</th>
								<th className="px-5 py-3 font-medium">Role</th>
								<th className="px-5 py-3 font-medium">Status</th>
								<th className="px-5 py-3 font-medium">Joined</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-zinc-100">
							{data.recentUsers.map((user) => (
								<tr key={user.id}>
									<td className="px-5 py-3 text-zinc-800">
										{user.email}
										{user.displayName ? (
											<span className="ml-2 text-xs text-zinc-400">
												{user.displayName}
											</span>
										) : null}
									</td>
									<td className="px-5 py-3">
										<Badge variant={user.role}>{statusLabel(user.role)}</Badge>
									</td>
									<td className="px-5 py-3">
										<Badge variant={user.status}>
											{statusLabel(user.status)}
										</Badge>
									</td>
									<td className="px-5 py-3 text-zinc-500">
										{formatDateTime(user.createdAt)}
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			</Card>
		</div>
	);
}
