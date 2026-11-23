import { useRouter } from "@tanstack/react-router";
import { useCallback, useState } from "react";

import { errorMessage } from "./utils";

/**
 * Small helper for wiring server-function calls to buttons/forms: tracks a
 * pending flag, surfaces errors, and invalidates the router so loaders re-run.
 */
export function useMutationAction() {
	const router = useRouter();
	const [pending, setPending] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const run = useCallback(
		async (
			action: () => Promise<unknown>,
			options: { invalidate?: boolean } = {},
		): Promise<boolean> => {
			setPending(true);
			setError(null);
			try {
				await action();
				if (options.invalidate !== false) {
					await router.invalidate();
				}
				return true;
			} catch (caught) {
				setError(errorMessage(caught));
				return false;
			} finally {
				setPending(false);
			}
		},
		[router],
	);

	return { pending, error, setError, run };
}
