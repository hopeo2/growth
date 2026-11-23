import { createMiddleware, createStart } from "@tanstack/react-start";

/**
 * Reject cross-origin state-changing requests. Server functions and server
 * routes are same-origin from the browser, so an `Origin` header that does not
 * match our app origin indicates CSRF. Requests without an `Origin` header
 * (SSR, internal calls, the Python worker using a bearer token) are allowed.
 */
const csrfGuard = createMiddleware().server(async ({ next, request }) => {
	const method = request.method.toUpperCase();
	if (method !== "GET" && method !== "HEAD") {
		const origin = request.headers.get("origin");
		const expected = process.env.APP_ORIGIN;
		if (
			origin &&
			expected &&
			new URL(origin).origin !== new URL(expected).origin
		) {
			return new Response("Cross-origin request blocked", { status: 403 });
		}
	}
	return next();
});

const securityHeaders = createMiddleware().server(async ({ next }) => {
	const result = await next();
	const response = result.response;
	if (response instanceof Response) {
		response.headers.set("X-Content-Type-Options", "nosniff");
		response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
		response.headers.set("X-Frame-Options", "DENY");
	}
	return result;
});

export const startInstance = createStart(() => ({
	requestMiddleware: [securityHeaders, csrfGuard],
}));
