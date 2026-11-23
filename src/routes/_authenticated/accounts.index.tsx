import { createFileRoute, Link } from "@tanstack/react-router";
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
	createAccountFn,
	listAccountsFn,
} from "@/functions/accounts.functions";
import { useMutationAction } from "@/lib/use-mutation";
import { formatDateTime, formatNumber, statusLabel } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/accounts/")({
	loader: () => listAccountsFn(),
	component: AccountsPage,
});

function AccountsPage() {
	const accounts = Route.useLoaderData();
	const createAccount = useServerFn(createAccountFn);
	const { pending, error, run } = useMutationAction();
	const [showForm, setShowForm] = useState(accounts.length === 0);
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [proxy, setProxy] = useState("");

	async function handleSubmit(event: FormEvent) {
		event.preventDefault();
		const ok = await run(() =>
			createAccount({
				data: { username, password, proxyUrl: proxy || undefined },
			}),
		);
		if (ok) {
			setUsername("");
			setPassword("");
			setProxy("");
			setShowForm(false);
		}
	}

	const totalFollowers = accounts.reduce(
		(sum, account) => sum + account.followers,
		0,
	);

	return (
		<div className="space-y-6">
			<PageHeader
				title="Accounts"
				description="Connect and manage the Instagram accounts the workers operate."
				action={
					<Button
						variant="outline"
						onClick={() => setShowForm((value) => !value)}
					>
						{showForm ? "Close" : "Add account"}
					</Button>
				}
			/>

			<div className="grid gap-4 sm:grid-cols-3">
				<StatCard
					label="Accounts"
					value={accounts.length}
					icon="👤"
					tone="indigo"
				/>
				<StatCard
					label="Active"
					value={
						accounts.filter((account) => account.status === "active").length
					}
					icon="✅"
					tone="emerald"
				/>
				<StatCard
					label="Total followers"
					value={formatNumber(totalFollowers)}
					icon="❤️"
					tone="amber"
				/>
			</div>

			{showForm ? (
				<Card>
					<CardHeader
						title="Add an Instagram account"
						description="Credentials are encrypted with AES-256-GCM before they are stored."
					/>
					<CardBody>
						<form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-3">
							{error ? (
								<div className="sm:col-span-3">
									<Alert>{error}</Alert>
								</div>
							) : null}
							<Field label="Instagram username">
								<Input
									required
									value={username}
									onChange={(event) => setUsername(event.target.value)}
									placeholder="studio.cafe"
								/>
							</Field>
							<Field label="Instagram password">
								<Input
									type="password"
									required
									value={password}
									onChange={(event) => setPassword(event.target.value)}
									placeholder="••••••••"
								/>
							</Field>
							<Field
								label="Proxy (optional)"
								hint="http://, https:// or socks5://"
							>
								<Input
									value={proxy}
									onChange={(event) => setProxy(event.target.value)}
									placeholder="socks5://user:pass@host:1080"
								/>
							</Field>
							<div className="flex items-end gap-3 sm:col-span-3">
								<Button type="submit" loading={pending}>
									Connect account
								</Button>
								<p className="text-xs text-zinc-500">
									A login check job runs immediately to verify the credentials.
								</p>
							</div>
						</form>
					</CardBody>
				</Card>
			) : null}

			{accounts.length === 0 ? (
				<Card>
					<EmptyState
						title="No accounts yet"
						description="Add your first Instagram account to start automating growth."
					/>
				</Card>
			) : (
				<Card>
					<CardHeader title="Connected accounts" />
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
									<th className="px-5 py-3 font-medium">Account</th>
									<th className="px-5 py-3 font-medium">Status</th>
									<th className="px-5 py-3 font-medium">Followers</th>
									<th className="px-5 py-3 font-medium">Growth</th>
									<th className="px-5 py-3 font-medium">Last run</th>
									<th className="px-5 py-3 font-medium text-right">Actions</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-zinc-100">
								{accounts.map((account) => (
									<tr key={account.id}>
										<td className="px-5 py-3">
											<Link
												to="/accounts/$accountId"
												params={{ accountId: account.id }}
												className="font-medium text-zinc-900 hover:text-indigo-600"
											>
												@{account.username}
											</Link>
										</td>
										<td className="px-5 py-3">
											<Badge variant={account.status}>
												{statusLabel(account.status)}
											</Badge>
										</td>
										<td className="px-5 py-3 text-zinc-600">
											{formatNumber(account.followers)}
										</td>
										<td className="px-5 py-3">
											{account.growthEnabled ? (
												<Badge variant="active">Enabled</Badge>
											) : (
												<Badge variant="paused">Disabled</Badge>
											)}
										</td>
										<td className="px-5 py-3 text-zinc-500">
											{account.lastRunAt
												? formatDateTime(account.lastRunAt)
												: "never"}
										</td>
										<td className="px-5 py-3">
											<div className="flex justify-end gap-2">
												<RunJobButton
													accountId={account.id}
													variant="outline"
													size="sm"
													label="Run"
												/>
												<Link
													to="/accounts/$accountId"
													params={{ accountId: account.id }}
													className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100"
												>
													Manage
												</Link>
											</div>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</Card>
			)}
		</div>
	);
}
