import {
	createFileRoute,
	Link,
	redirect,
	useRouter,
} from "@tanstack/react-router";
import { type FormEvent, useState } from "react";

import { Alert, Button, Field, Input } from "@/components/ui";
import { getPublicConfig } from "@/lib/auth.functions";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import { errorMessage } from "@/lib/utils";

export const Route = createFileRoute("/signup")({
	loader: () => getPublicConfig(),
	beforeLoad: ({ context }) => {
		if (context.session) {
			throw redirect({ to: "/dashboard" });
		}
	},
	component: SignupPage,
});

function SignupPage() {
	const router = useRouter();
	const config = Route.useLoaderData();
	const [displayName, setDisplayName] = useState("");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	async function handleSubmit(event: FormEvent) {
		event.preventDefault();
		setError(null);
		setNotice(null);
		setLoading(true);
		try {
			const supabase = createSupabaseBrowserClient();
			const { data, error: signUpError } = await supabase.auth.signUp({
				email,
				password,
				options: { data: { display_name: displayName } },
			});
			if (signUpError) throw new Error(signUpError.message);

			if (data.session) {
				await router.invalidate();
				await router.navigate({ to: "/dashboard" });
				return;
			}
			setNotice(
				"Account created. Check your inbox to confirm your email address, then log in.",
			);
		} catch (caught) {
			setError(errorMessage(caught));
		} finally {
			setLoading(false);
		}
	}

	return (
		<div className="flex min-h-screen items-center justify-center px-4 py-10">
			<div className="w-full max-w-sm">
				<Link to="/" className="mb-6 flex items-center justify-center gap-2">
					<span className="flex size-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
						G
					</span>
					<span className="text-lg font-semibold">Growly</span>
				</Link>

				<div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
					<h1 className="text-lg font-semibold">Create your account</h1>
					<p className="mt-1 text-sm text-zinc-500">
						Start automating Instagram growth in a few minutes.
					</p>

					{!config.registrationOpen ? (
						<div className="mt-5">
							<Alert tone="warning">
								Registration is currently closed. Please try again later.
							</Alert>
						</div>
					) : (
						<form onSubmit={handleSubmit} className="mt-5 space-y-4">
							{error ? <Alert>{error}</Alert> : null}
							{notice ? <Alert tone="success">{notice}</Alert> : null}
							<Field label="Name">
								<Input
									required
									value={displayName}
									onChange={(event) => setDisplayName(event.target.value)}
									placeholder="Jane Doe"
								/>
							</Field>
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
							<Field label="Password" hint="At least 8 characters">
								<Input
									type="password"
									required
									minLength={8}
									autoComplete="new-password"
									value={password}
									onChange={(event) => setPassword(event.target.value)}
									placeholder="••••••••"
								/>
							</Field>
							<Button type="submit" loading={loading} className="w-full">
								Create account
							</Button>
						</form>
					)}

					<p className="mt-5 text-center text-sm text-zinc-500">
						Already registered?{" "}
						<Link to="/login" className="font-medium text-indigo-600">
							Log in
						</Link>
					</p>
				</div>
			</div>
		</div>
	);
}
