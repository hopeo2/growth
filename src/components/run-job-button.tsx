import { useServerFn } from "@tanstack/react-start";

import { Button } from "@/components/ui";
import { enqueueJobFn } from "@/functions/jobs.functions";
import { useMutationAction } from "@/lib/use-mutation";

export function RunJobButton({
	accountId,
	type = "growth_run",
	label = "Run now",
	variant = "primary",
	size = "md",
}: {
	accountId: string;
	type?: "growth_run" | "account_sync" | "login_check";
	label?: string;
	variant?: "primary" | "outline" | "secondary" | "ghost";
	size?: "sm" | "md" | "lg";
}) {
	const enqueueJob = useServerFn(enqueueJobFn);
	const { pending, run } = useMutationAction();

	return (
		<Button
			variant={variant}
			size={size}
			loading={pending}
			onClick={() => run(() => enqueueJob({ data: { accountId, type } }))}
		>
			{label}
		</Button>
	);
}
