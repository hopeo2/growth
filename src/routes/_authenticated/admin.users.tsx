import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { type FormEvent, useState } from "react";

import {
	Alert,
	Badge,
	Button,
	Card,
	CardHeader,
	Input,
	PageHeader,
} from "@/components/ui";
import { applyUserActionFn, listAllUsersFn } from "@/functions/admin.functions";
import { useMutationAction } from "@/lib/use-mutation";
import { formatDateTime, statusLabel } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/admin/users")({
	validateSearch: (search: Record<string, unknown>): { q?: string } => ({
		q: typeof search.q === "string" ? search.q : "",
	}),
	loaderDeps: ({ search }) => ({ q: search.q }),
	loader: ({ deps }) =>
		listAllUsersFn({ data: { query: deps.q || undefined } }),
	component: AdminUsersPage,
});

function AdminUsersPage() {
	const users = Route.useLoaderData();
	const search = Route.useSearch();
	const navigate = useNavigate();
	const applyAction = useServerFn(applyUserActionFn);
	const { pending, error, run } = useMutationAction();
	const [query, setQuery] = useState(search.q);

	function handleSearch(event: FormEvent) {
		event.preventDefault();
		navigate({ to: "/admin/users", search: { q: query } });
	}

	return (
		<div className="space-y-6">
			<PageHeader
				title="Users"
				description="Suspend accounts or grant administrator access."
				action={
					<form onSubmit={handleSearch} className="flex items-center gap-2">
						<Input
							value={query}
							onChange={(event) => setQuery(event.target.value)}
							placeholder="Search email or name"
							className="w-56"
						/>
						<Button type="submit" variant="outline">
							Search
						</Button>
					</form>
				}
			/>

			{error ? <Alert>{error}</Alert> : null}

			<Card>
				<CardHeader title={`${users.length} user(s)`} />
				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-zinc-100 text-left text-xs uppercase text-zinc-400">
								<th className="px-5 py-3 font-medium">User</th>
								<th className="px-5 py-3 font-medium">Role</th>
								<th className="px-5 py-3 font-medium">Status</th>
								<th className="px-5 py-3 font-medium">Accounts</th>
								<th className="px-5 py-3 font-medium">Joined</th>
								<th className="px-5 py-3 font-medium text-right">Actions</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-zinc-100">
							{users.map((user) => (
								<tr key={user.id}>
									<td className="px-5 py-3">
										<p className="font-medium text-zinc-800">{user.email}</p>
										{user.displayName ? (
											<p className="text-xs text-zinc-400">
												{user.displayName}
											</p>
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
									<td className="px-5 py-3 text-zinc-600">
										{user.accountCount}
									</td>
									<td className="px-5 py-3 text-zinc-500">
										{formatDateTime(user.createdAt)}
									</td>
									<td className="px-5 py-3">
										<div className="flex flex-wrap justify-end gap-2">
											{user.status === "active" ? (
												<Button
													size="sm"
													variant="outline"
													disabled={pending}
													onClick={() =>
														run(() =>
															applyAction({
																data: { userId: user.id, action: "suspend" },
															}),
														)
													}
												>
													Suspend
												</Button>
											) : (
												<Button
													size="sm"
													variant="outline"
													disabled={pending}
													onClick={() =>
														run(() =>
															applyAction({
																data: { userId: user.id, action: "activate" },
															}),
														)
													}
												>
													Activate
												</Button>
											)}
											{user.role === "admin" ? (
												<Button
													size="sm"
													variant="ghost"
													disabled={pending}
													onClick={() =>
														run(() =>
															applyAction({
																data: { userId: user.id, action: "demote" },
															}),
														)
													}
												>
													Demote
												</Button>
											) : (
												<Button
													size="sm"
													variant="ghost"
													disabled={pending}
													onClick={() =>
														run(() =>
															applyAction({
																data: { userId: user.id, action: "promote" },
															}),
														)
													}
												>
													Make admin
												</Button>
											)}
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
