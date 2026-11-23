import type {
	ButtonHTMLAttributes,
	InputHTMLAttributes,
	ReactNode,
	SelectHTMLAttributes,
	TextareaHTMLAttributes,
} from "react";

import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */

export function Card({
	children,
	className,
}: {
	children: ReactNode;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"rounded-xl border border-zinc-200 bg-white shadow-sm",
				className,
			)}
		>
			{children}
		</div>
	);
}

export function CardHeader({
	title,
	description,
	action,
	className,
}: {
	title: ReactNode;
	description?: ReactNode;
	action?: ReactNode;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"flex flex-wrap items-start justify-between gap-3 border-b border-zinc-100 px-5 py-4",
				className,
			)}
		>
			<div>
				<h2 className="text-sm font-semibold text-zinc-900">{title}</h2>
				{description ? (
					<p className="mt-0.5 text-xs text-zinc-500">{description}</p>
				) : null}
			</div>
			{action}
		</div>
	);
}

export function CardBody({
	children,
	className,
}: {
	children: ReactNode;
	className?: string;
}) {
	return <div className={cn("px-5 py-4", className)}>{children}</div>;
}

/* ------------------------------------------------------------------ */
/* Button                                                              */
/* ------------------------------------------------------------------ */

type ButtonVariant =
	| "primary"
	| "secondary"
	| "outline"
	| "ghost"
	| "danger"
	| "success";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
	primary:
		"bg-indigo-600 text-white hover:bg-indigo-500 focus-visible:outline-indigo-600",
	secondary:
		"bg-zinc-900 text-white hover:bg-zinc-800 focus-visible:outline-zinc-900",
	outline:
		"border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 focus-visible:outline-zinc-400",
	ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900",
	danger:
		"bg-red-600 text-white hover:bg-red-500 focus-visible:outline-red-600",
	success:
		"bg-emerald-600 text-white hover:bg-emerald-500 focus-visible:outline-emerald-600",
};

export function Button({
	variant = "primary",
	size = "md",
	loading = false,
	className,
	children,
	disabled,
	...props
}: {
	variant?: ButtonVariant;
	size?: "sm" | "md" | "lg";
	loading?: boolean;
	children: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
	const sizes = {
		sm: "px-2.5 py-1.5 text-xs",
		md: "px-3.5 py-2 text-sm",
		lg: "px-4 py-2.5 text-sm",
	};
	return (
		<button
			{...props}
			disabled={disabled || loading}
			className={cn(
				"inline-flex items-center justify-center gap-2 rounded-lg font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
				BUTTON_VARIANTS[variant],
				sizes[size],
				className,
			)}
		>
			{loading ? (
				<span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
			) : null}
			{children}
		</button>
	);
}

/* ------------------------------------------------------------------ */
/* Form fields                                                         */
/* ------------------------------------------------------------------ */

export function Field({
	label,
	hint,
	error,
	children,
	className,
}: {
	label: ReactNode;
	hint?: ReactNode;
	error?: ReactNode;
	children: ReactNode;
	className?: string;
}) {
	return (
		// biome-ignore lint/a11y/noLabelWithoutControl: the control is passed via `children`
		<label className={cn("block", className)}>
			<span className="mb-1.5 block text-xs font-medium text-zinc-700">
				{label}
			</span>
			{children}
			{hint ? (
				<span className="mt-1 block text-xs text-zinc-400">{hint}</span>
			) : null}
			{error ? (
				<span className="mt-1 block text-xs text-red-600">{error}</span>
			) : null}
		</label>
	);
}

const inputClasses =
	"w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm outline-none transition placeholder:text-zinc-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-zinc-50";

export function Input({
	className,
	...props
}: InputHTMLAttributes<HTMLInputElement>) {
	return <input {...props} className={cn(inputClasses, className)} />;
}

export function Textarea({
	className,
	...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
	return (
		<textarea {...props} className={cn(inputClasses, "min-h-20", className)} />
	);
}

export function Select({
	className,
	children,
	...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
	return (
		<select {...props} className={cn(inputClasses, "pr-8", className)}>
			{children}
		</select>
	);
}

export function Checkbox({
	label,
	...props
}: { label: ReactNode } & InputHTMLAttributes<HTMLInputElement>) {
	return (
		<label className="inline-flex cursor-pointer items-center gap-2 text-sm text-zinc-700">
			<input
				type="checkbox"
				{...props}
				className="size-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
			/>
			{label}
		</label>
	);
}

/* ------------------------------------------------------------------ */
/* Badge                                                               */
/* ------------------------------------------------------------------ */

const BADGE_VARIANTS: Record<string, string> = {
	active: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
	succeeded: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
	online: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
	idle: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
	running: "bg-blue-50 text-blue-700 ring-blue-600/20",
	busy: "bg-blue-50 text-blue-700 ring-blue-600/20",
	queued: "bg-amber-50 text-amber-700 ring-amber-600/20",
	pending: "bg-amber-50 text-amber-700 ring-amber-600/20",
	paused: "bg-zinc-100 text-zinc-600 ring-zinc-500/20",
	canceled: "bg-zinc-100 text-zinc-600 ring-zinc-500/20",
	offline: "bg-zinc-100 text-zinc-600 ring-zinc-500/20",
	error: "bg-red-50 text-red-700 ring-red-600/20",
	failed: "bg-red-50 text-red-700 ring-red-600/20",
	suspended: "bg-red-50 text-red-700 ring-red-600/20",
	warning: "bg-amber-50 text-amber-700 ring-amber-600/20",
	verification_required: "bg-amber-50 text-amber-700 ring-amber-600/20",
	admin: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
	like: "bg-pink-50 text-pink-700 ring-pink-600/20",
	follow: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
	unfollow: "bg-amber-50 text-amber-700 ring-amber-600/20",
	comment: "bg-sky-50 text-sky-700 ring-sky-600/20",
	story: "bg-violet-50 text-violet-700 ring-violet-600/20",
	login: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
	info: "bg-zinc-100 text-zinc-600 ring-zinc-500/20",
	default: "bg-zinc-100 text-zinc-700 ring-zinc-500/20",
};

export function Badge({
	children,
	variant,
	className,
}: {
	children: ReactNode;
	variant?: string;
	className?: string;
}) {
	const key = variant ?? "default";
	return (
		<span
			className={cn(
				"inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
				BADGE_VARIANTS[key] ?? BADGE_VARIANTS.default,
				className,
			)}
		>
			{children}
		</span>
	);
}

/* ------------------------------------------------------------------ */
/* Stat card                                                           */
/* ------------------------------------------------------------------ */

export function StatCard({
	label,
	value,
	hint,
	icon,
	tone = "default",
}: {
	label: string;
	value: ReactNode;
	hint?: ReactNode;
	icon?: ReactNode;
	tone?: "default" | "indigo" | "emerald" | "amber" | "red";
}) {
	const tones = {
		default: "bg-zinc-100 text-zinc-600",
		indigo: "bg-indigo-50 text-indigo-600",
		emerald: "bg-emerald-50 text-emerald-600",
		amber: "bg-amber-50 text-amber-600",
		red: "bg-red-50 text-red-600",
	};
	return (
		<Card>
			<div className="flex items-start justify-between gap-3 px-5 py-4">
				<div>
					<p className="text-xs font-medium tracking-wide text-zinc-500 uppercase">
						{label}
					</p>
					<p className="mt-1.5 text-2xl font-semibold text-zinc-900">{value}</p>
					{hint ? <p className="mt-1 text-xs text-zinc-500">{hint}</p> : null}
				</div>
				{icon ? (
					<span
						className={cn(
							"flex size-9 items-center justify-center rounded-lg text-base",
							tones[tone],
						)}
					>
						{icon}
					</span>
				) : null}
			</div>
		</Card>
	);
}

/* ------------------------------------------------------------------ */
/* Misc                                                                */
/* ------------------------------------------------------------------ */

export function Alert({
	tone = "error",
	children,
}: {
	tone?: "error" | "success" | "info" | "warning";
	children: ReactNode;
}) {
	const tones = {
		error: "border-red-200 bg-red-50 text-red-700",
		success: "border-emerald-200 bg-emerald-50 text-emerald-700",
		info: "border-blue-200 bg-blue-50 text-blue-700",
		warning: "border-amber-200 bg-amber-50 text-amber-800",
	};
	return (
		<div className={cn("rounded-lg border px-3.5 py-2.5 text-sm", tones[tone])}>
			{children}
		</div>
	);
}

export function EmptyState({
	title,
	description,
	action,
}: {
	title: string;
	description?: string;
	action?: ReactNode;
}) {
	return (
		<div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
			<p className="text-sm font-medium text-zinc-800">{title}</p>
			{description ? (
				<p className="max-w-sm text-xs text-zinc-500">{description}</p>
			) : null}
			{action}
		</div>
	);
}

export function Spinner({ className }: { className?: string }) {
	return (
		<span
			className={cn(
				"inline-block size-4 animate-spin rounded-full border-2 border-zinc-300 border-t-indigo-600",
				className,
			)}
		/>
	);
}

export function PageHeader({
	title,
	description,
	action,
}: {
	title: string;
	description?: string;
	action?: ReactNode;
}) {
	return (
		<div className="flex flex-wrap items-end justify-between gap-3">
			<div>
				<h1 className="text-xl font-semibold text-zinc-900">{title}</h1>
				{description ? (
					<p className="mt-1 text-sm text-zinc-500">{description}</p>
				) : null}
			</div>
			{action}
		</div>
	);
}
