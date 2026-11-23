import { createFileRoute, Link } from "@tanstack/react-router";

export const Route = createFileRoute("/")({ component: LandingPage });

const FEATURES = [
	{
		title: "Account management",
		body: "Connect Instagram accounts, store credentials encrypted, and watch login health in real time.",
		icon: "🔐",
	},
	{
		title: "Growth automation",
		body: "InstaPy workers like, follow, comment and watch stories on a safe, human-like schedule.",
		icon: "⚙️",
	},
	{
		title: "Analytics & logs",
		body: "Daily interaction charts plus a full activity log of every action the worker performed.",
		icon: "📈",
	},
];

const STEPS = [
	"Create your account and add an Instagram profile.",
	"Pick hashtags, target audiences and daily limits.",
	"The scheduler queues a job; a Python worker runs InstaPy.",
	"Watch results land on your dashboard in real time.",
];

function LandingPage() {
	const { session } = Route.useRouteContext();

	return (
		<div className="min-h-screen bg-gradient-to-b from-white to-zinc-50">
			<header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
				<div className="flex items-center gap-2">
					<span className="flex size-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
						G
					</span>
					<span className="text-lg font-semibold">Growly</span>
				</div>
				<nav className="flex items-center gap-3 text-sm">
					{session ? (
						<Link
							to="/dashboard"
							className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500"
						>
							Open dashboard
						</Link>
					) : (
						<>
							<Link
								to="/login"
								className="rounded-lg px-4 py-2 font-medium text-zinc-700 hover:bg-zinc-100"
							>
								Log in
							</Link>
							<Link
								to="/signup"
								className="rounded-lg bg-indigo-600 px-4 py-2 font-medium text-white hover:bg-indigo-500"
							>
								Get started
							</Link>
						</>
					)}
				</nav>
			</header>

			<main className="mx-auto max-w-6xl px-6 pb-20">
				<section className="grid items-center gap-10 py-16 lg:grid-cols-2">
					<div>
						<span className="inline-flex items-center rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-600/20 ring-inset">
							Powered by InstaPy
						</span>
						<h1 className="mt-5 text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl">
							Grow Instagram accounts on autopilot
						</h1>
						<p className="mt-5 max-w-xl text-lg text-zinc-600">
							A multi-tenant control panel for InstaPy: users manage accounts
							and growth settings, admins run the platform, and a worker fleet
							executes the automation.
						</p>
						<div className="mt-8 flex flex-wrap gap-3">
							<Link
								to={session ? "/dashboard" : "/signup"}
								className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium text-white hover:bg-indigo-500"
							>
								{session ? "Go to dashboard" : "Create an account"}
							</Link>
							<Link
								to="/login"
								className="rounded-lg border border-zinc-300 px-5 py-2.5 font-medium text-zinc-700 hover:bg-zinc-50"
							>
								Log in
							</Link>
						</div>
					</div>

					<div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
						<div className="flex items-center justify-between border-b border-zinc-100 pb-4">
							<div>
								<p className="text-xs font-medium text-zinc-500 uppercase">
									Interactions this week
								</p>
								<p className="mt-1 text-3xl font-semibold text-zinc-900">
									1,284
								</p>
							</div>
							<span className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
								+18%
							</span>
						</div>
						<div className="mt-5 grid grid-cols-3 gap-3 text-center">
							{[
								{ label: "Likes", value: "812" },
								{ label: "Follows", value: "296" },
								{ label: "Comments", value: "176" },
							].map((item) => (
								<div
									key={item.label}
									className="rounded-lg bg-zinc-50 px-3 py-4"
								>
									<p className="text-xl font-semibold text-zinc-900">
										{item.value}
									</p>
									<p className="text-xs text-zinc-500">{item.label}</p>
								</div>
							))}
						</div>
						<div className="mt-5 space-y-2 border-t border-zinc-100 pt-4 text-xs text-zinc-500">
							<p>✅ @studio.cafe — liked 24 posts on #coffeelover</p>
							<p>✅ @studio.cafe — followed 6 accounts, stories watched</p>
							<p className="text-amber-600">🕒 Next run scheduled in 2h 15m</p>
						</div>
					</div>
				</section>

				<section className="grid gap-5 sm:grid-cols-3">
					{FEATURES.map((feature) => (
						<div
							key={feature.title}
							className="rounded-xl border border-zinc-200 bg-white p-6"
						>
							<span className="text-2xl">{feature.icon}</span>
							<h2 className="mt-4 font-semibold text-zinc-900">
								{feature.title}
							</h2>
							<p className="mt-2 text-sm text-zinc-600">{feature.body}</p>
						</div>
					))}
				</section>

				<section className="mt-16 rounded-2xl border border-zinc-200 bg-white p-8">
					<h2 className="text-xl font-semibold text-zinc-900">How it works</h2>
					<ol className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
						{STEPS.map((step, index) => (
							<li key={step} className="flex gap-3">
								<span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
									{index + 1}
								</span>
								<span className="text-sm text-zinc-600">{step}</span>
							</li>
						))}
					</ol>
				</section>
			</main>

			<footer className="border-t border-zinc-200 py-6 text-center text-xs text-zinc-400">
				Growly · Instagram automation panel built on InstaPy
			</footer>
		</div>
	);
}
