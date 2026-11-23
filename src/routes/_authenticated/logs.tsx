import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { AccountPicker } from "@/components/account-picker";
import {
	Badge,
	Card,
	CardHeader,
	EmptyState,
	PageHeader,
	Select,
} from "@/components/ui";
import { listAccountsFn } from "@/functions/accounts.functions";
import { listActivityLogsFn } from "@/functions/logs.functions";
import { formatDateTime } from "@/lib/utils";

const ACTIONS = [
	"like",
	"follow",
	"unfollow",
	"comment",
	"story",
	"login",
	"info",
	"warning",
	"error",
] as const;

type LogAction = (typeof ACTIONS)[number];

export const Route = createFileRoute("/_authenticated/logs")({
	validateSearch: (
		search: Record<string, unknown>,
	): { account?: string; action?: LogAction } => ({
		account: typeof search.account === "string" ? search.account : undefined,
		action:
			typeof search.action === "string" &&
			(ACTIONS as readonly string[]).includes(search.action)
				? (search.action as LogAction)
				: undefined,
	}),
	loaderDeps: ({ search }) => ({
		account: search.account,
		action: search.action,
	}),
	loader: async ({ deps }) => {
		const [accounts, logs] = await Promise.all([
			listAccountsFn(),
			listActivityLogsFn({
				data: {
					accountId: deps.account,
					actions: deps.action ? [deps.action] : undefined,
					limit: 200,
				},
			}),
		]);
		return { accounts, logs };
	},
	component: LogsPage,
});

function LogsPage() {
	const { accounts, logs } = Route.useLoaderData();
	const navigate = useNavigate();
	const search = Route.useSearch();

	return (
		<div className="space-y-6">
			<PageHeader
				title="Activity logs"
				description="Every action the automation workers performed."
				action={
					<div className="flex flex-wrap items-center gap-3">
						<Select
							value={search.action ?? "all"}
							onChange={(event) =>
								navigate({
									to: "/logs",
									search: {
										account: search.account,
										action:
											event.target.value === "all"
												? undefined
												: (event.target.value as LogAction),
									},
								})
							}
							className="w-40"
						>
							<option value="all">All actions</option>
							{ACTIONS.map((action) => (
								<option key={action} value={action}>
									{action}
								</option>
							))}
						</Select>
						<AccountPicker
							accounts={accounts}
							value={search.account}
							onChange={(account) =>
								navigate({
									to: "/logs",
									search: { account, action: search.action },
								})
							}
						/>
					</div>
				}
			/>

			<Card>
				<CardHeader title={`${logs.length} entries`} />
				{logs.length === 0 ? (
					<EmptyState
						title="No matching activity"
						description="Run a growth job or adjust the filters above."
					/>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
									<th className="px-5 py-3 font-medium">Time</th>
									<th className="px-5 py-3 font-medium">Action</th>
									<th className="px-5 py-3 font-medium">Target</th>
									<th className="px-5 py-3 font-medium">Details</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-zinc-100">
								{logs.map((log) => (
									<tr key={log.id}>
										<td className="whitespace-nowrap px-5 py-2.5 text-zinc-500">
											{formatDateTime(log.createdAt)}
										</td>
										<td className="px-5 py-2.5">
											<Badge variant={log.action}>{log.action}</Badge>
										</td>
										<td className="px-5 py-2.5 text-zinc-700">
											{log.target ?? "—"}
										</td>
										<td className="px-5 py-2.5 text-zinc-500">
											{log.message ?? "—"}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</Card>
		</div>
	);
}
