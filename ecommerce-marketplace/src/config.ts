export interface Config {
  HOST: string;
  PORT: number;
  DATABASE_PATH: string;
  SESSION_TTL_HOURS: number;
  SECURE_COOKIES: boolean;
}

export function loadConfig(environment: NodeJS.ProcessEnv = process.env): Config {
  const port = Number(environment.PORT ?? "3001");
  const ttl = Number(environment.SESSION_TTL_HOURS ?? "12");
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("PORT must be between 1 and 65535");
  if (!Number.isInteger(ttl) || ttl < 1 || ttl > 168) throw new Error("SESSION_TTL_HOURS must be between 1 and 168");
  const databasePath = environment.DATABASE_PATH ?? "./data/marketplace.sqlite";
  if (databasePath.length === 0 || databasePath.length > 1000) throw new Error("DATABASE_PATH is invalid");
  const host = environment.HOST ?? "127.0.0.1";
  if (host.trim().length === 0 || host.length > 253 || /[\s/]/.test(host)) throw new Error("HOST is invalid");
  const secure = environment.SECURE_COOKIES ?? "false";
  if (secure !== "true" && secure !== "false") throw new Error("SECURE_COOKIES must be true or false");
  return { HOST: host, PORT: port, DATABASE_PATH: databasePath, SESSION_TTL_HOURS: ttl, SECURE_COOKIES: secure === "true" };
}
