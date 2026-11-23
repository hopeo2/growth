import { Select } from "@/components/ui";
import type { AccountSummary } from "@/server/accounts.server";

export function AccountPicker({
	accounts,
	value,
	onChange,
}: {
	accounts: AccountSummary[];
	value: string | undefined;
	onChange: (accountId: string) => void;
}) {
	if (accounts.length === 0) return null;
	return (
		<div className="flex items-center gap-2">
			<span className="text-xs font-medium text-zinc-500">Account</span>
			<Select
				value={value ?? accounts[0]?.id}
				onChange={(event) => onChange(event.target.value)}
				className="w-56"
			>
				{accounts.map((account) => (
					<option key={account.id} value={account.id}>
						@{account.username}
					</option>
				))}
			</Select>
		</div>
	);
}
