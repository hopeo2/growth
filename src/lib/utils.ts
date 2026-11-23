export function cn(
	...classes: Array<string | false | null | undefined>
): string {
	return classes.filter(Boolean).join(" ");
}

const numberFormatter = new Intl.NumberFormat("en-US");

export function formatNumber(value: number | null | undefined): string {
	if (value === null || value === undefined) return "—";
	return numberFormatter.format(value);
}

export function formatCompact(value: number | null | undefined): string {
	if (value === null || value === undefined) return "—";
	return new Intl.NumberFormat("en-US", {
		notation: "compact",
		maximumFractionDigits: 1,
	}).format(value);
}

function toDate(value: Date | string | null | undefined): Date | null {
	if (!value) return null;
	const date = value instanceof Date ? value : new Date(value);
	return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(
	value: Date | string | null | undefined,
): string {
	const date = toDate(value);
	if (!date) return "—";
	return date.toLocaleString("en-GB", {
		year: "numeric",
		month: "short",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
	});
}

export function formatDay(value: Date | string | null | undefined): string {
	const date = toDate(value);
	if (!date) return "—";
	return date.toLocaleDateString("en-GB", {
		month: "short",
		day: "2-digit",
	});
}

export function relativeTime(value: Date | string | null | undefined): string {
	const date = toDate(value);
	if (!date) return "never";
	const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
	const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
	const thresholds: Array<[Intl.RelativeTimeFormatUnit, number]> = [
		["second", 60],
		["minute", 60],
		["hour", 24],
		["day", 30],
		["month", 12],
		["year", Number.POSITIVE_INFINITY],
	];
	let amount = diffSeconds;
	for (const [unit, limit] of thresholds) {
		if (Math.abs(amount) < limit)
			return formatter.format(Math.round(amount), unit);
		amount /= limit;
	}
	return formatter.format(Math.round(amount), "year");
}

const STATUS_LABELS: Record<string, string> = {
	pending: "Pending",
	active: "Active",
	paused: "Paused",
	error: "Error",
	verification_required: "Verification required",
	queued: "Queued",
	running: "Running",
	succeeded: "Succeeded",
	failed: "Failed",
	canceled: "Canceled",
	suspended: "Suspended",
	online: "Online",
	idle: "Idle",
	busy: "Busy",
	offline: "Offline",
	user: "User",
	admin: "Admin",
};

export function statusLabel(status: string | null | undefined): string {
	if (!status) return "—";
	return STATUS_LABELS[status] ?? status;
}

export function errorMessage(error: unknown): string {
	if (error instanceof Error) return error.message;
	if (typeof error === "string") return error;
	return "Something went wrong";
}

export function initials(value: string): string {
	const trimmed = value.trim();
	if (!trimmed) return "?";
	return trimmed.slice(0, 2).toUpperCase();
}
