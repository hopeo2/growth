import {
	createFileRoute,
	Link,
	redirect,
	useRouter,
} from "@tanstack/react-router";
import { type FormEvent, useState } from "react";

import { Alert, Button, Field, Input } from "@/components/ui";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import { errorMessage } from "@/lib/utils";

function sanitizeRedirect(value: unknown): string {
	if (
		typeof value !== "string" ||
		!value.startsWith("/") ||
		value.startsWith("//")
	) {
		return "/dashboard";
	}
	return value;
}

export const Route = createFileRoute("/login")({
	validateSearch: (search: Record<string, unknown>): { redirect?: string } => ({
		redirect: sanitizeRedirect(search.redirect),
	}),
	beforeLoad: ({ context, search }) => {
		if (context.session) {
			throw redirect({ to: search.redirect ?? "/dashboard" });
		}
	},
	component: LoginPage,
});

function LoginPage() {
	const router = useRouter();
	const search = Route.useSearch();
	const redirectTo = search.redirect ?? "/dashboard";
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	async function handleSubmit(event: FormEvent) {
		event.preventDefault();
		setError(null);
		setLoading(true);
		try {
			const supabase = createSupabaseBrowserClient();
			const { error: signInError } = await supabase.auth.signInWithPassword({
				email,
				password,
			});
			if (signInError) throw new Error(signInError.message);
			await router.invalidate();
			await router.navigate({ to: redirectTo });
		} catch (caught) {
			setError(errorMessage(caught));
		} finally {
			setLoading(false);
		}
	}

	return (
		<div className="flex min-h-screen items-center justify-center px-4">
			<div className="w-full max-w-sm">
				<Link to="/" className="mb-6 flex items-center justify-center gap-2">
					<span className="flex size-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
						G
					</span>
					<span className="text-lg font-semibold">Growly</span>
				</Link>

				<div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
					<h1 className="text-lg font-semibold">Welcome back</h1>
					<p className="mt-1 text-sm text-zinc-500">
						Log in to manage your Instagram accounts.
					</p>

					<form onSubmit={handleSubmit} className="mt-5 space-y-4">
						{error ? <Alert>{error}</Alert> : null}
						<Field label="Email">
							<Input
								type="email"
								required
								autoComplete="email"
								value={email}
								onChange={(event) => setEmail(event.target.value)}
								placeholder="you@example.com"
							/>
						</Field>
						<Field label="Password">
							<Input
								type="password"
								required
								autoComplete="current-password"
								value={password}
								onChange={(event) => setPassword(event.target.value)}
								placeholder="••••••••"
							/>
						</Field>
						<Button type="submit" loading={loading} className="w-full">
							Log in
						</Button>
					</form>

					<p className="mt-5 text-center text-sm text-zinc-500">
						No account yet?{" "}
						<Link to="/signup" className="font-medium text-indigo-600">
							Sign up
						</Link>
					</p>
				</div>
			</div>
		</div>
	);
}
