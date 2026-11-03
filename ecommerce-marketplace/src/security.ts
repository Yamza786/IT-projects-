import { createHash, randomBytes, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";

const keyLength = 64;
const dummyHash = `scrypt$16384$8$1$${"00".repeat(16)}$${"00".repeat(keyLength)}`;

function deriveKey(password: string, salt: Buffer): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scryptCallback(password, salt, keyLength, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 }, (error, derived) => {
      if (error) reject(error);
      else resolve(derived);
    });
  });
}

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const derived = await deriveKey(password, salt);
  return `scrypt$16384$8$1$${salt.toString("hex")}$${derived.toString("hex")}`;
}

export async function verifyPassword(password: string, stored: string | undefined): Promise<boolean> {
  const encoded = stored ?? dummyHash;
  const parts = encoded.split("$");
  if (parts.length !== 6 || parts[0] !== "scrypt" || parts[1] !== "16384" || parts[2] !== "8" || parts[3] !== "1" || !/^[0-9a-f]{32}$/.test(parts[4] ?? "") || !/^[0-9a-f]{128}$/.test(parts[5] ?? "")) return false;
  const expected = Buffer.from(parts[5]!, "hex");
  const actual = await deriveKey(password, Buffer.from(parts[4]!, "hex"));
  return timingSafeEqual(actual, expected) && stored !== undefined;
}

export function createSessionToken(): string {
  return randomBytes(32).toString("base64url");
}

export function digestSessionToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}
