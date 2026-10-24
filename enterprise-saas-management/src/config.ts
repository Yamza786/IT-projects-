import { z } from "zod";

const schema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),
  DATABASE_PATH: z.string().min(1).default("./data/saas.sqlite"),
  SESSION_TTL_HOURS: z.coerce.number().int().min(1).max(168).default(12),
  COOKIE_SECURE: z.enum(["true", "false"]).default("false").transform((value) => value === "true"),
  BOOTSTRAP_EMAIL: z.string().email().optional(),
  BOOTSTRAP_PASSWORD: z.string().min(12).optional(),
}).refine((value) => Boolean(value.BOOTSTRAP_EMAIL) === Boolean(value.BOOTSTRAP_PASSWORD), {
  message: "BOOTSTRAP_EMAIL and BOOTSTRAP_PASSWORD must be set together",
});

export type AppConfig = z.infer<typeof schema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  return schema.parse(env);
}
