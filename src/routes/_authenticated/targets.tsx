import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { type FormEvent, useState } from "react";

import { AccountPicker } from "@/components/account-picker";
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
	Select,
} from "@/components/ui";
import type { Target } from "@/db";
import { listAccountsFn } from "@/functions/accounts.functions";
import {
	addTargetFn,
	listTargetsFn,
	removeTargetFn,
	toggleTargetFn,
} from "@/functions/targets.functions";
import { useMutationAction } from "@/lib/use-mutation";
import type { AccountSummary } from "@/server/accounts.server";

export const Route = createFileRoute("/_authenticated/targets")({
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
		const targets = accountId
			? await listTargetsFn({ data: { accountId } })
			: [];
		return { accounts, accountId, targets };
	},
	component: TargetsPage,
});

type TargetKind = "hashtag" | "username" | "location";

const KIND_LABELS: Record<TargetKind, string> = {
	hashtag: "Hashtags",
	username: "Audience (users)",
	location: "Locations",
};

function TargetsPage() {
	const { accounts, accountId, targets } = Route.useLoaderData();
	const navigate = useNavigate();

	if (!accountId) {
		return (
			<div className="space-y-6">
				<PageHeader title="Targets" />
				<Card>
					<EmptyState
						title="Add an account first"
						description="Hashtags and audiences are configured per account."
					/>
				</Card>
			</div>
		);
	}

	return (
		<TargetsManager
			key={accountId}
			accounts={accounts}
			accountId={accountId}
			targets={targets}
			onAccountChange={(next) =>
				navigate({ to: "/targets", search: { account: next } })
			}
		/>
	);
}

function TargetsManager({
	accounts,
	accountId,
	targets,
	onAccountChange,
}: {
	accounts: AccountSummary[];
	accountId: string;
	targets: Target[];
	onAccountChange: (accountId: string) => void;
}) {
	const addTarget = useServerFn(addTargetFn);
	const removeTarget = useServerFn(removeTargetFn);
	const toggleTarget = useServerFn(toggleTargetFn);
	const { pending, error, run } = useMutationAction();

	const [kind, setKind] = useState<TargetKind>("hashtag");
	const [value, setValue] = useState("");
	const [bulk, setBulk] = useState("");

	async function handleAdd(event: FormEvent) {
		event.preventDefault();
		const ok = await run(() => addTarget({ data: { accountId, kind, value } }));
		if (ok) setValue("");
	}

	async function handleBulkAdd() {
		const entries = bulk
			.split(/[\n,]/)
			.map((entry) => entry.replace(/^#+/, "").trim())
			.filter(Boolean);
		if (entries.length === 0) return;
		const ok = await run(async () => {
			for (const entry of entries) {
				await addTarget({ data: { accountId, kind: "hashtag", value: entry } });
			}
		});
		if (ok) setBulk("");
	}

	const grouped: Record<TargetKind, Target[]> = {
		hashtag: targets.filter((target) => target.kind === "hashtag"),
		username: targets.filter((target) => target.kind === "username"),
		location: targets.filter((target) => target.kind === "location"),
	};

	const username =
		accounts.find((account) => account.id === accountId)?.username ?? "";

	return (
		<div className="space-y-6">
			<PageHeader
				title="Targets"
				description={`Hashtags and audiences for @${username}`}
				action={
					<AccountPicker
						accounts={accounts}
						value={accountId}
						onChange={onAccountChange}
					/>
				}
			/>

			{error ? <Alert>{error}</Alert> : null}

			<Card>
				<CardHeader
					title="Add a target"
					description="Hashtags drive likes/follows; users power the interact activity."
				/>
				<CardBody className="space-y-5">
					<form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3">
						<Field label="Type">
							<Select
								value={kind}
								onChange={(event) => setKind(event.target.value as TargetKind)}
							>
								<option value="hashtag">Hashtag</option>
								<option value="username">User</option>
								<option value="location">Location</option>
							</Select>
						</Field>
						<Field label="Value" className="min-w-56 flex-1">
							<Input
								required
								value={value}
								onChange={(event) => setValue(event.target.value)}
								placeholder={
									kind === "hashtag"
										? "coffeelover"
										: kind === "username"
											? "some.creator"
											: "berlin"
								}
							/>
						</Field>
						<Button type="submit" loading={pending}>
							Add target
						</Button>
					</form>

					<div className="border-t border-zinc-100 pt-4">
						<Field
							label="Bulk add hashtags"
							hint="One per line or comma separated"
						>
							<textarea
								className="min-h-20 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
								value={bulk}
								onChange={(event) => setBulk(event.target.value)}
								placeholder={"coffee\nspecialtycoffee\ncafevibes"}
							/>
						</Field>
						<div className="mt-3">
							<Button
								type="button"
								variant="outline"
								onClick={handleBulkAdd}
								loading={pending}
							>
								Add hashtags
							</Button>
						</div>
					</div>
				</CardBody>
			</Card>

			{(Object.keys(grouped) as TargetKind[]).map((groupKind) => (
				<Card key={groupKind}>
					<CardHeader
						title={KIND_LABELS[groupKind]}
						description={`${grouped[groupKind].length} target(s)`}
					/>
					<CardBody>
						{grouped[groupKind].length === 0 ? (
							<p className="text-sm text-zinc-500">
								No {groupKind} targets yet.
							</p>
						) : (
							<div className="flex flex-wrap gap-2">
								{grouped[groupKind].map((target) => (
									<span
										key={target.id}
										className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 py-1 pl-3 pr-1 text-sm"
									>
										<span
											className={
												target.enabled
													? "text-zinc-800"
													: "text-zinc-400 line-through"
											}
										>
											{target.kind === "hashtag"
												? `#${target.value}`
												: target.value}
										</span>
										{!target.enabled ? (
											<Badge variant="paused">off</Badge>
										) : null}
										<button
											type="button"
											onClick={() =>
												run(() =>
													toggleTarget({
														data: {
															accountId,
															targetId: target.id,
															enabled: !target.enabled,
														},
													}),
												)
											}
											className="rounded-md px-2 py-0.5 text-xs text-zinc-500 hover:bg-zinc-200"
										>
											{target.enabled ? "Disable" : "Enable"}
										</button>
										<button
											type="button"
											onClick={() =>
												run(() =>
													removeTarget({
														data: { accountId, targetId: target.id },
													}),
												)
											}
											className="rounded-md px-2 py-0.5 text-xs text-red-600 hover:bg-red-50"
										>
											Remove
										</button>
									</span>
								))}
							</div>
						)}
					</CardBody>
				</Card>
			))}
		</div>
	);
}
