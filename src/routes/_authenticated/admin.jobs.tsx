import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";

import {
	Alert,
	Badge,
	Button,
	Card,
	CardHeader,
	EmptyState,
	PageHeader,
} from "@/components/ui";
import { forceJobActionFn, listAllJobsFn } from "@/functions/admin.functions";
import { useMutationAction } from "@/lib/use-mutation";
import { formatDateTime, relativeTime, statusLabel } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/admin/jobs")({
	loader: () => listAllJobsFn(),
	component: AdminJobsPage,
});

function AdminJobsPage() {
	const jobs = Route.useLoaderData();
	const forceAction = useServerFn(forceJobActionFn);
	const { pending, error, run } = useMutationAction();

	return (
		<div className="space-y-6">
			<PageHeader
				title="Jobs"
				description="Inspect and intervene in the automation queue."
			/>

			{error ? <Alert>{error}</Alert> : null}

			<Card>
				<CardHeader title={`${jobs.length} job(s)`} />
				{jobs.length === 0 ? (
					<EmptyState
						title="Queue is empty"
						description="Jobs appear when users enqueue runs or the scheduler fires."
					/>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
									<th className="px-5 py-3 font-medium">Type</th>
									<th className="px-5 py-3 font-medium">Status</th>
									<th className="px-5 py-3 font-medium">Progress</th>
									<th className="px-5 py-3 font-medium">Attempts</th>
									<th className="px-5 py-3 font-medium">Created</th>
									<th className="px-5 py-3 font-medium">Worker</th>
									<th className="px-5 py-3 font-medium text-right">Actions</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-zinc-100">
								{jobs.map((job) => (
									<tr key={job.id}>
										<td className="px-5 py-3 text-zinc-800">
											{job.type.replace("_", " ")}
											{job.error ? (
												<p className="max-w-xs truncate text-xs text-red-600">
													{job.error}
												</p>
											) : null}
										</td>
										<td className="px-5 py-3">
											<Badge variant={job.status}>
												{statusLabel(job.status)}
											</Badge>
										</td>
										<td className="px-5 py-3 text-zinc-600">{job.progress}%</td>
										<td className="px-5 py-3 text-zinc-600">
											{job.attempts}/{job.maxAttempts}
										</td>
										<td className="px-5 py-3 text-zinc-500">
											{relativeTime(job.createdAt)}
											<span className="block text-xs text-zinc-400">
												{formatDateTime(job.createdAt)}
											</span>
										</td>
										<td className="px-5 py-3 text-zinc-500">
											{job.lockedBy ?? "—"}
										</td>
										<td className="px-5 py-3">
											<div className="flex justify-end gap-2">
												<Button
													size="sm"
													variant="outline"
													disabled={pending}
													onClick={() =>
														run(() =>
															forceAction({
																data: { jobId: job.id, action: "retry" },
															}),
														)
													}
												>
													Retry
												</Button>
												<Button
													size="sm"
													variant="ghost"
													disabled={pending}
													onClick={() =>
														run(() =>
															forceAction({
																data: { jobId: job.id, action: "cancel" },
															}),
														)
													}
												>
													Cancel
												</Button>
											</div>
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
