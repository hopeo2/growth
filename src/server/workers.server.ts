import { desc, eq } from "drizzle-orm";

import { getDb, workers } from "@/db";

export interface WorkerRegistration {
	name: string;
	version?: string;
	concurrency?: number;
}

/** Upsert a worker heartbeat row. */
export async function registerHeartbeat(
	registration: WorkerRegistration,
	patch: {
		status?: "online" | "idle" | "busy" | "offline";
		currentJobId?: string | null;
	} = {},
): Promise<void> {
	const db = getDb();
	await db
		.insert(workers)
		.values({
			name: registration.name,
			version: registration.version ?? null,
			concurrency: registration.concurrency ?? 1,
			status: patch.status ?? "online",
			currentJobId: patch.currentJobId ?? null,
			lastHeartbeatAt: new Date(),
		})
		.onConflictDoUpdate({
			target: workers.name,
			set: {
				version: registration.version ?? null,
				concurrency: registration.concurrency ?? 1,
				status: patch.status ?? "online",
				currentJobId: patch.currentJobId ?? null,
				lastHeartbeatAt: new Date(),
			},
		});
}

export async function markWorkerOffline(name: string): Promise<void> {
	const db = getDb();
	await db
		.update(workers)
		.set({ status: "offline", currentJobId: null, lastHeartbeatAt: new Date() })
		.where(eq(workers.name, name));
}

export async function listWorkers() {
	const db = getDb();
	return db.select().from(workers).orderBy(desc(workers.lastHeartbeatAt));
}
