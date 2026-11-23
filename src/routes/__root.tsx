import { createRootRoute, HeadContent, Scripts } from "@tanstack/react-router";

import { getCurrentUser } from "@/lib/auth.functions";
import appCss from "../styles.css?url";

export const Route = createRootRoute({
	head: () => ({
		meta: [
			{ charSet: "utf-8" },
			{ name: "viewport", content: "width=device-width, initial-scale=1" },
			{ title: "Growly — Instagram growth automation" },
			{
				name: "description",
				content:
					"Manage Instagram accounts, automate growth tasks with InstaPy, and track the results.",
			},
		],
		links: [{ rel: "stylesheet", href: appCss }],
	}),
	beforeLoad: async () => ({ session: await getCurrentUser() }),
	shellComponent: RootDocument,
});

function RootDocument({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en">
			<head>
				<HeadContent />
			</head>
			<body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased">
				{children}
				<Scripts />
			</body>
		</html>
	);
}
