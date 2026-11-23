import {
	createFileRoute,
	Link,
	notFound,
	useRouter,
} from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { type FormEvent, useState } from "react";

import { RunJobButton } from "@/components/run-job-button";
import {
	Alert,
	Badge,
	Button,
	Card,
	CardBody,
	CardHeader,
	EmptyState,
	Field,
	Input,
	PageHeader,
	StatCard,
} from "@/components/ui";
import {
	deleteAccountFn,
	getAccountFn,
	updateAccountCredentialsFn,
	updateAccountFn,
} from "@/functions/accounts.functions";
import { listAccountJobsFn } from "@/functions/jobs.functions";
import { useMutationAction } from "@/lib/use-mutation";
import {
	formatDateTime,
	formatNumber,
	relativeTime,
	statusLabel,
} from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/accounts/$accountId")({
	loader: async ({ params }) => {
		const [account, jobs] = await Promise.all([
			getAccountFn({ data: { accountId: params.accountId } }),
			listAccountJobsFn({ data: { accountId: params.accountId } }),
		]);
		if (!account) throw notFound();
		return { account, jobs };
	},
	component: AccountDetailPage,
});

function AccountDetailPage() {
	const { account, jobs } = Route.useLoaderData();
	const router = useRouter();
	const updateAccount = useServerFn(updateAccountFn);
	const updateCredentials = useServerFn(updateAccountCredentialsFn);
	const deleteAccount = useServerFn(deleteAccountFn);
	const { pending, error, run } = useMutationAction();
	const [password, setPassword] = useState("");
	const [proxy, setProxy] = useState(account.proxyUrl ?? "");

	async function handlePassword(event: FormEvent) {
		event.preventDefault();
		const ok = await run(() =>
			updateCredentials({ data: { accountId: account.id, password } }),
		);
		if (ok) setPassword("");
	}

	async function handleProxy(event: FormEvent) {
		event.preventDefault();
		await run(() =>
			updateAccount({
				data: {
					accountId: account.id,
					proxyUrl: proxy || undefined,
				},
			}),
		);
	}

	async function handleToggleStatus() {
		const next = account.status === "paused" ? "active" : "paused";
		await run(() =>
			updateAccount({
				data: {
					accountId: account.id,
					proxyUrl: account.proxyUrl ?? undefined,
					status: next,
				},
			}),
		);
	}

	async function handleDelete() {
		if (
			!window.confirm(`Delete @${account.username}? This cannot be undone.`)
		) {
			return;
		}
		const ok = await run(() =>
			deleteAccount({ data: { accountId: account.id } }),
		);
		if (ok) await router.navigate({ to: "/accounts" });
	}

	return (
		<div className="space-y-6">
			<div className="flex flex-wrap items-center gap-3">
				<Link
					to="/accounts"
					className="text-sm text-zinc-500 hover:text-zinc-800"
				>
					← Accounts
				</Link>
			</div>

			<PageHeader
				title={`@${account.username}`}
				description={`Added ${formatDateTime(account.createdAt)}`}
				action={
					<div className="flex flex-wrap gap-2">
						<RunJobButton accountId={account.id} label="Run growth" />
						<RunJobButton
							accountId={account.id}
							type="login_check"
							label="Verify login"
							variant="outline"
						/>
						<Button
							variant="outline"
							onClick={handleToggleStatus}
							loading={pending}
						>
							{account.status === "paused" ? "Resume" : "Pause"}
						</Button>
					</div>
				}
			/>

			{error ? <Alert>{error}</Alert> : null}
			{account.lastError ? (
				<Alert tone="warning">Last error: {account.lastError}</Alert>
			) : null}

			<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<StatCard
					label="Status"
					value={
						<Badge variant={account.status}>
							{statusLabel(account.status)}
						</Badge>
					}
					icon="🔐"
				/>
				<StatCard
					label="Followers"
					value={formatNumber(account.followers)}
					icon="❤️"
					tone="amber"
				/>
				<StatCard
					label="Following"
					value={formatNumber(account.following)}
					icon="➡️"
				/>
				<StatCard label="Posts" value={formatNumber(account.posts)} icon="🖼️" />
			</div>

			<div className="grid gap-6 lg:grid-cols-2">
				<Card>
					<CardHeader
						title="Growth configuration"
						description="Daily limits, targets and filters for this account."
					/>
					<CardBody className="space-y-3 text-sm">
						<div className="flex items-center justify-between">
							<span className="text-zinc-500">Growth automation</span>
							<Badge variant={account.growthEnabled ? "active" : "paused"}>
								{account.growthEnabled ? "Enabled" : "Disabled"}
							</Badge>
						</div>
						<div className="flex items-center justify-between">
							<span className="text-zinc-500">Last run</span>
							<span className="text-zinc-700">
								{account.lastRunAt ? relativeTime(account.lastRunAt) : "never"}
							</span>
						</div>
						<div className="flex items-center justify-between">
							<span className="text-zinc-500">Last login</span>
							<span className="text-zinc-700">
								{account.lastLoginAt
									? relativeTime(account.lastLoginAt)
									: "never"}
							</span>
						</div>
						<div className="flex gap-2 pt-2">
							<Link
								to="/settings"
								search={{ account: account.id }}
								className="rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-500"
							>
								Growth settings
							</Link>
							<Link
								to="/targets"
								search={{ account: account.id }}
								className="rounded-lg border border-zinc-300 px-3.5 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
							>
								Targets
							</Link>
						</div>
					</CardBody>
				</Card>

				<div className="space-y-6">
					<Card>
						<CardHeader
							title="Update password"
							description="Replace the stored Instagram password."
						/>
						<CardBody>
							<form onSubmit={handlePassword} className="flex items-end gap-3">
								<Field label="New password" className="flex-1">
									<Input
										type="password"
										required
										value={password}
										onChange={(event) => setPassword(event.target.value)}
										placeholder="••••••••"
									/>
								</Field>
								<Button type="submit" loading={pending}>
									Save
								</Button>
							</form>
						</CardBody>
					</Card>

					<Card>
						<CardHeader
							title="Proxy"
							description="Route requests through a proxy."
						/>
						<CardBody>
							<form onSubmit={handleProxy} className="flex items-end gap-3">
								<Field label="Proxy URL" className="flex-1">
									<Input
										value={proxy}
										onChange={(event) => setProxy(event.target.value)}
										placeholder="socks5://user:pass@host:1080"
									/>
								</Field>
								<Button type="submit" variant="outline" loading={pending}>
									Save
								</Button>
							</form>
						</CardBody>
					</Card>
				</div>
			</div>

			<Card>
				<CardHeader title="Recent jobs" />
				{jobs.length === 0 ? (
					<EmptyState title="No jobs yet" />
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
									<th className="px-5 py-3 font-medium">Type</th>
									<th className="px-5 py-3 font-medium">Status</th>
									<th className="px-5 py-3 font-medium">Progress</th>
									<th className="px-5 py-3 font-medium">Created</th>
									<th className="px-5 py-3 font-medium">Error</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-zinc-100">
								{jobs.map((job) => (
									<tr key={job.id}>
										<td className="px-5 py-3 text-zinc-800">
											{job.type.replace("_", " ")}
										</td>
										<td className="px-5 py-3">
											<Badge variant={job.status}>
												{statusLabel(job.status)}
											</Badge>
										</td>
										<td className="px-5 py-3 text-zinc-600">{job.progress}%</td>
										<td className="px-5 py-3 text-zinc-500">
											{formatDateTime(job.createdAt)}
										</td>
										<td className="px-5 py-3 text-xs text-red-600">
											{job.error ? job.error.slice(0, 80) : "—"}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</Card>

			<Card>
				<CardHeader title="Danger zone" />
				<CardBody className="flex items-center justify-between gap-4">
					<p className="text-sm text-zinc-500">
						Deleting the account removes its settings, targets, jobs and logs.
					</p>
					<Button variant="danger" onClick={handleDelete} loading={pending}>
						Delete account
					</Button>
				</CardBody>
			</Card>
		</div>
	);
}
