import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";

import {
	Alert,
	Badge,
	Button,
	Card,
	CardHeader,
	PageHeader,
} from "@/components/ui";
import {
	applyAccountActionFn,
	listAllAccountsFn,
} from "@/functions/admin.functions";
import { useMutationAction } from "@/lib/use-mutation";
import { formatDateTime, formatNumber, statusLabel } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/admin/accounts")({
	loader: () => listAllAccountsFn(),
	component: AdminAccountsPage,
});

function AdminAccountsPage() {
	const accounts = Route.useLoaderData();
	const applyAction = useServerFn(applyAccountActionFn);
	const { pending, error, run } = useMutationAction();

	return (
		<div className="space-y-6">
			<PageHeader
				title="Accounts"
				description="Every Instagram account on the platform."
			/>

			{error ? <Alert>{error}</Alert> : null}

			<Card>
				<CardHeader title={`${accounts.length} account(s)`} />
				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
								<th className="px-5 py-3 font-medium">Account</th>
								<th className="px-5 py-3 font-medium">Owner</th>
								<th className="px-5 py-3 font-medium">Status</th>
								<th className="px-5 py-3 font-medium">Followers</th>
								<th className="px-5 py-3 font-medium">Last run</th>
								<th className="px-5 py-3 font-medium text-right">Actions</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-zinc-100">
							{accounts.map((account) => (
								<tr key={account.id}>
									<td className="px-5 py-3">
										<p className="font-medium text-zinc-800">
											@{account.username}
										</p>
										{account.lastError ? (
											<p className="max-w-xs truncate text-xs text-red-600">
												{account.lastError}
											</p>
										) : null}
									</td>
									<td className="px-5 py-3 text-zinc-600">
										{account.ownerEmail ?? "—"}
									</td>
									<td className="px-5 py-3">
										<Badge variant={account.status}>
											{statusLabel(account.status)}
										</Badge>
									</td>
									<td className="px-5 py-3 text-zinc-600">
										{formatNumber(account.followers)}
									</td>
									<td className="px-5 py-3 text-zinc-500">
										{formatDateTime(account.lastRunAt)}
									</td>
									<td className="px-5 py-3">
										<div className="flex flex-wrap justify-end gap-2">
											{account.status === "paused" ? (
												<Button
													size="sm"
													variant="outline"
													disabled={pending}
													onClick={() =>
														run(() =>
															applyAction({
																data: {
																	accountId: account.id,
																	action: "activate",
																},
															}),
														)
													}
												>
													Activate
												</Button>
											) : (
												<Button
													size="sm"
													variant="outline"
													disabled={pending}
													onClick={() =>
														run(() =>
															applyAction({
																data: {
																	accountId: account.id,
																	action: "pause",
																},
															}),
														)
													}
												>
													Pause
												</Button>
											)}
											<Button
												size="sm"
												variant="ghost"
												disabled={pending}
												onClick={() =>
													run(() =>
														applyAction({
															data: {
																accountId: account.id,
																action: "reset_error",
															},
														}),
													)
												}
											>
												Reset error
											</Button>
										</div>
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
