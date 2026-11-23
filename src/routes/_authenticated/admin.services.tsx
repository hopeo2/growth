import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { type FormEvent, useState } from "react";

import {
	Alert,
	Button,
	Card,
	CardBody,
	CardHeader,
	Checkbox,
	Field,
	Input,
	PageHeader,
} from "@/components/ui";
import {
	getServiceSettingsFn,
	updateServiceSettingsFn,
} from "@/functions/admin.functions";
import { useMutationAction } from "@/lib/use-mutation";
import { formatDateTime } from "@/lib/utils";

export const Route = createFileRoute("/_authenticated/admin/services")({
	loader: () => getServiceSettingsFn(),
	component: AdminServicesPage,
});

function AdminServicesPage() {
	const settings = Route.useLoaderData();
	const saveSettings = useServerFn(updateServiceSettingsFn);
	const { pending, error, run } = useMutationAction();
	const [saved, setSaved] = useState(false);
	const [form, setForm] = useState({
		workerEnabled: settings.workerEnabled,
		maintenanceMode: settings.maintenanceMode,
		registrationOpen: settings.registrationOpen,
		maxAccountsPerUser: settings.maxAccountsPerUser,
		defaultLikesPerDay: settings.defaultLikesPerDay,
		defaultFollowsPerDay: settings.defaultFollowsPerDay,
		defaultUnfollowsPerDay: settings.defaultUnfollowsPerDay,
		defaultCommentsPerDay: settings.defaultCommentsPerDay,
	});

	const patch = (values: Partial<typeof form>) =>
		setForm((current) => ({ ...current, ...values }));

	async function handleSubmit(event: FormEvent) {
		event.preventDefault();
		setSaved(false);
		const ok = await run(() => saveSettings({ data: form }));
		setSaved(ok);
	}

	return (
		<form onSubmit={handleSubmit} className="space-y-6">
			<PageHeader
				title="Service settings"
				description="Global switches and defaults for the platform."
				action={
					<Button type="submit" loading={pending}>
						Save
					</Button>
				}
			/>

			{error ? <Alert>{error}</Alert> : null}
			{saved ? <Alert tone="success">Service settings saved.</Alert> : null}

			<Card>
				<CardHeader title="Switches" />
				<CardBody className="space-y-3">
					<Checkbox
						label="Worker queue enabled (workers may claim jobs)"
						checked={form.workerEnabled}
						onChange={(event) => patch({ workerEnabled: event.target.checked })}
					/>
					<Checkbox
						label="Maintenance mode"
						checked={form.maintenanceMode}
						onChange={(event) =>
							patch({ maintenanceMode: event.target.checked })
						}
					/>
					<Checkbox
						label="Registration open"
						checked={form.registrationOpen}
						onChange={(event) =>
							patch({ registrationOpen: event.target.checked })
						}
					/>
				</CardBody>
			</Card>

			<Card>
				<CardHeader
					title="Limits & defaults"
					description="Applied when a user adds a new account."
				/>
				<CardBody className="grid gap-4 sm:grid-cols-3">
					<Field label="Max accounts per user" hint="0 = unlimited">
						<Input
							type="number"
							min={0}
							value={form.maxAccountsPerUser}
							onChange={(event) =>
								patch({ maxAccountsPerUser: Number(event.target.value) })
							}
						/>
					</Field>
					<Field label="Default likes / day">
						<Input
							type="number"
							min={0}
							value={form.defaultLikesPerDay}
							onChange={(event) =>
								patch({ defaultLikesPerDay: Number(event.target.value) })
							}
						/>
					</Field>
					<Field label="Default follows / day">
						<Input
							type="number"
							min={0}
							value={form.defaultFollowsPerDay}
							onChange={(event) =>
								patch({ defaultFollowsPerDay: Number(event.target.value) })
							}
						/>
					</Field>
					<Field label="Default unfollows / day">
						<Input
							type="number"
							min={0}
							value={form.defaultUnfollowsPerDay}
							onChange={(event) =>
								patch({ defaultUnfollowsPerDay: Number(event.target.value) })
							}
						/>
					</Field>
					<Field label="Default comments / day">
						<Input
							type="number"
							min={0}
							value={form.defaultCommentsPerDay}
							onChange={(event) =>
								patch({ defaultCommentsPerDay: Number(event.target.value) })
							}
						/>
					</Field>
				</CardBody>
			</Card>

			<p className="text-xs text-zinc-400">
				Last updated {formatDateTime(settings.updatedAt)}
			</p>

			<div className="flex justify-end">
				<Button type="submit" loading={pending}>
					Save
				</Button>
			</div>
		</form>
	);
}
