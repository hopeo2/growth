import {
	createCipheriv,
	createDecipheriv,
	randomBytes,
	timingSafeEqual,
} from "node:crypto";

import { serverEnv } from "./env.server";

/**
 * AES-256-GCM secret encryption for Instagram credentials.
 *
 * Wire format (must stay byte-compatible with `worker/crypto.py`):
 *
 *   v1.<iv>.<ciphertext>.<tag>
 *
 * where each part is unpadded base64url. The IV is 12 bytes (GCM standard)
 * and the tag is 16 bytes.
 */

const VERSION = "v1";
const IV_BYTES = 12;

function getKey(): Buffer {
	const raw = serverEnv.encryptionKey;
	const key = Buffer.from(raw, "base64");
	if (key.length !== 32) {
		throw new Error(
			"CREDENTIALS_ENCRYPTION_KEY must be 32 bytes encoded as base64 (generate with: openssl rand -base64 32).",
		);
	}
	return key;
}

export function encryptSecret(plaintext: string): string {
	const iv = randomBytes(IV_BYTES);
	const cipher = createCipheriv("aes-256-gcm", getKey(), iv);
	const ciphertext = Buffer.concat([
		cipher.update(plaintext, "utf8"),
		cipher.final(),
	]);
	const tag = cipher.getAuthTag();

	return [
		VERSION,
		iv.toString("base64url"),
		ciphertext.toString("base64url"),
		tag.toString("base64url"),
	].join(".");
}

export function decryptSecret(payload: string): string {
	const parts = payload.split(".");
	if (parts.length !== 4 || parts[0] !== VERSION) {
		throw new Error("Malformed encrypted payload");
	}

	const [, ivPart, ciphertextPart, tagPart] = parts;
	const iv = Buffer.from(ivPart, "base64url");
	const ciphertext = Buffer.from(ciphertextPart, "base64url");
	const tag = Buffer.from(tagPart, "base64url");

	const decipher = createDecipheriv("aes-256-gcm", getKey(), iv);
	decipher.setAuthTag(tag);
	return Buffer.concat([
		decipher.update(ciphertext),
		decipher.final(),
	]).toString("utf8");
}

/** Constant-time comparison for shared tokens (worker API). */
export function safeEqual(a: string, b: string): boolean {
	const bufA = Buffer.from(a);
	const bufB = Buffer.from(b);
	if (bufA.length !== bufB.length) return false;
	return timingSafeEqual(bufA, bufB);
}
