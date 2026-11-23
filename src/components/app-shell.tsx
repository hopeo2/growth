import { Link, useRouter, useRouterState } from "@tanstack/react-router";
import { type ReactNode, useState } from "react";

import type { SessionUser } from "@/lib/auth.server";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import { cn, initials } from "@/lib/utils";

const ICON_PATHS: Record<string, string> = {
	dashboard:
		"M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75",
	accounts:
		"M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z",
	settings:
		"M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75",
	targets:
		"M12 21a9 9 0 100-18 9 9 0 000 18zm0-5a4 4 0 100-8 4 4 0 000 8zm0-3a1 1 0 100-2 1 1 0 000 2z",
	analytics:
		"M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z",
	logs: "M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z",
	admin:
		"M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z",
	jobs: "M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5",
	services:
		"M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3V5.25a3 3 0 013-3h13.5a3 3 0 013 3v6a3 3 0 01-3 3m-13.5 0v3.75a3 3 0 003 3h7.5a3 3 0 003-3v-3.75",
	logout:
		"M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75",
};

function Icon({ name, className }: { name: string; className?: string }) {
	const path = ICON_PATHS[name];
	if (!path) return null;
	return (
		<svg
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth={1.6}
			strokeLinecap="round"
			strokeLinejoin="round"
			className={cn("size-5", className)}
			aria-hidden="true"
		>
			<path d={path} />
		</svg>
	);
}

interface NavItem {
	to: string;
	label: string;
	icon: string;
	adminOnly?: boolean;
}

const PRIMARY_NAV: NavItem[] = [
	{ to: "/dashboard", label: "Dashboard", icon: "dashboard" },
	{ to: "/accounts", label: "Accounts", icon: "accounts" },
	{ to: "/settings", label: "Growth settings", icon: "settings" },
	{ to: "/targets", label: "Targets", icon: "targets" },
	{ to: "/analytics", label: "Analytics", icon: "analytics" },
	{ to: "/logs", label: "Activity logs", icon: "logs" },
];

const ADMIN_NAV: NavItem[] = [
	{ to: "/admin", label: "Overview", icon: "admin", adminOnly: true },
	{ to: "/admin/users", label: "Users", icon: "accounts", adminOnly: true },
	{
		to: "/admin/accounts",
		label: "Accounts",
		icon: "settings",
		adminOnly: true,
	},
	{ to: "/admin/jobs", label: "Jobs", icon: "jobs", adminOnly: true },
	{
		to: "/admin/services",
		label: "Services",
		icon: "services",
		adminOnly: true,
	},
];

function NavLink({
	item,
	active,
	onNavigate,
}: {
	item: NavItem;
	active: boolean;
	onNavigate?: () => void;
}) {
	return (
		<Link
			to={item.to}
			onClick={onNavigate}
			className={cn(
				"flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
				active
					? "bg-indigo-50 text-indigo-700"
					: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900",
			)}
		>
			<Icon name={item.icon} />
			{item.label}
		</Link>
	);
}

export function AppShell({
	session,
	children,
}: {
	session: SessionUser;
	children: ReactNode;
}) {
	const pathname = useRouterState({
		select: (state) => state.location.pathname,
	});
	const router = useRouter();
	const [mobileOpen, setMobileOpen] = useState(false);

	const isActive = (to: string) =>
		to === "/admin" ? pathname === "/admin" : pathname.startsWith(to);

	async function handleLogout() {
		const supabase = createSupabaseBrowserClient();
		await supabase.auth.signOut();
		await router.invalidate();
		await router.navigate({ to: "/login" });
	}

	const sidebar = (
		<div className="flex h-full flex-col">
			<Link
				to="/dashboard"
				className="flex items-center gap-2 px-4 py-5"
				onClick={() => setMobileOpen(false)}
			>
				<span className="flex size-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
					G
				</span>
				<span className="text-base font-semibold text-zinc-900">Growly</span>
			</Link>

			<nav className="flex-1 space-y-1 px-3">
				{PRIMARY_NAV.map((item) => (
					<NavLink
						key={item.to}
						item={item}
						active={isActive(item.to)}
						onNavigate={() => setMobileOpen(false)}
					/>
				))}

				{session.role === "admin" ? (
					<>
						<p className="mt-5 px-3 pb-1 text-xs font-semibold tracking-wide text-zinc-400 uppercase">
							Administration
						</p>
						{ADMIN_NAV.map((item) => (
							<NavLink
								key={item.to}
								item={item}
								active={isActive(item.to)}
								onNavigate={() => setMobileOpen(false)}
							/>
						))}
					</>
				) : null}
			</nav>

			<div className="border-t border-zinc-200 p-3">
				<div className="flex items-center gap-3 rounded-lg px-2 py-2">
					<span className="flex size-9 items-center justify-center rounded-full bg-zinc-200 text-xs font-semibold text-zinc-700">
						{initials(session.displayName ?? session.email)}
					</span>
					<div className="min-w-0 flex-1">
						<p className="truncate text-sm font-medium text-zinc-800">
							{session.displayName ?? session.email}
						</p>
						<p className="truncate text-xs text-zinc-500">
							{session.role === "admin" ? "Administrator" : "Member"}
						</p>
					</div>
				</div>
				<button
					type="button"
					onClick={handleLogout}
					className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
				>
					<Icon name="logout" />
					Log out
				</button>
			</div>
		</div>
	);

	return (
		<div className="flex min-h-screen">
			<aside className="hidden w-64 shrink-0 border-r border-zinc-200 bg-white lg:block">
				<div className="sticky top-0 h-screen">{sidebar}</div>
			</aside>

			{mobileOpen ? (
				<div className="fixed inset-0 z-40 lg:hidden">
					<button
						type="button"
						aria-label="Close navigation"
						className="absolute inset-0 bg-zinc-900/40"
						onClick={() => setMobileOpen(false)}
					/>
					<div className="absolute inset-y-0 left-0 w-64 bg-white shadow-xl">
						{sidebar}
					</div>
				</div>
			) : null}

			<div className="flex min-w-0 flex-1 flex-col">
				<header className="flex items-center gap-3 border-b border-zinc-200 bg-white px-4 py-3 lg:hidden">
					<button
						type="button"
						onClick={() => setMobileOpen(true)}
						className="rounded-lg p-2 text-zinc-600 hover:bg-zinc-100"
						aria-label="Open navigation"
					>
						<svg
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							strokeWidth={1.8}
							className="size-5"
							aria-hidden="true"
						>
							<path
								strokeLinecap="round"
								d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
							/>
						</svg>
					</button>
					<span className="text-base font-semibold">Growly</span>
				</header>

				<main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-8">
					{children}
				</main>
			</div>
		</div>
	);
}
