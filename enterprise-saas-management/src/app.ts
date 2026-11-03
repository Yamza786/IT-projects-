import { randomUUID } from "node:crypto";
import cookieParser from "cookie-parser";
import express, { type ErrorRequestHandler, type Request, type Response } from "express";
import helmet from "helmet";
import { z } from "zod";
import { requireAuth, requirePlatformAdmin, requireTenantRole, type TenantRole } from "./auth.js";
import type { Database } from "./database.js";
import { hashPassword, newSessionToken, digestToken, verifyPassword } from "./security.js";

const loginSchema = z.object({ email: z.string().email().max(254), password: z.string().min(1).max(256) });
const userSchema = z.object({ email: z.string().email().max(254), password: z.string().min(12).max(256) });
const tenantSchema = z.object({
  name: z.string().trim().min(1).max(120),
  slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/).min(2).max(60),
});
const memberSchema = z.object({ email: z.string().email().max(254), role: z.enum(["ADMIN", "BILLING", "MEMBER", "VIEWER"]) });
const subscriptionSchema = z.object({
  plan: z.enum(["FREE", "STARTER", "GROWTH", "ENTERPRISE"]),
  status: z.enum(["TRIAL", "ACTIVE", "PAST_DUE", "CANCELED"]),
  seats: z.number().int().min(1).max(100000),
});
const DUMMY_PASSWORD_HASH = `scrypt$16384$8$1$${"00".repeat(16)}$${"00".repeat(64)}`;

interface AppOptions {
  db: Database;
  sessionTtlHours: number;
  secureCookies: boolean;
  bootstrapEmail?: string;
  bootstrapPassword?: string;
}

function routeParam(req: Request, key: string): string {
  const value = req.params[key];
  return typeof value === "string" ? value : Array.isArray(value) ? value[0] ?? "" : "";
}

function audit(db: Database, actorId: string | null, tenantId: string | null, action: string, targetId: string | null, details: unknown = {}): void {
  db.prepare(`INSERT INTO audit_events (id, actor_user_id, tenant_id, action, target_id, details_json)
    VALUES (?, ?, ?, ?, ?, ?)`)
    .run(randomUUID(), actorId, tenantId, action, targetId, JSON.stringify(details));
}

function parseBody<T>(schema: z.ZodType<T>, req: Request, res: Response): T | undefined {
  const parsed = schema.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid request", issues: parsed.error.issues.map(({ path, message }) => ({ path, message })) });
    return undefined;
  }
  return parsed.data;
}

export async function createApp(options: AppOptions) {
  const { db } = options;
  const app = express();
  app.disable("x-powered-by");
  app.use(helmet({ contentSecurityPolicy: false }));
  app.use(express.json({ limit: "32kb", strict: true }));
  app.use(cookieParser());
  app.use((req, res, next) => {
    const started = Date.now();
    res.on("finish", () => {
      process.stdout.write(`${JSON.stringify({ level: "info", event: "http_request", method: req.method, path: req.path, status: res.statusCode, duration_ms: Date.now() - started })}\n`);
    });
    next();
  });

  if (options.bootstrapEmail && options.bootstrapPassword) {
    const exists = db.prepare("SELECT 1 FROM users WHERE email = ? COLLATE NOCASE").get(options.bootstrapEmail);
    if (!exists) {
      const userId = randomUUID();
      const passwordHash = await hashPassword(options.bootstrapPassword);
      db.prepare("INSERT INTO users (id, email, password_hash, platform_admin) VALUES (?, ?, ?, 1)")
        .run(userId, options.bootstrapEmail.toLowerCase(), passwordHash);
      audit(db, userId, null, "platform.bootstrap_admin_created", userId);
    }
  }

  const auth = requireAuth(db);
  app.get("/health", (_req, res) => res.json({ status: "ok" }));

  app.post("/auth/login", async (req, res, next) => {
    try {
      const body = parseBody(loginSchema, req, res);
      if (!body) return;
      const user = db.prepare("SELECT id, email, password_hash AS passwordHash FROM users WHERE email = ? COLLATE NOCASE")
        .get(body.email) as { id: string; email: string; passwordHash: string } | undefined;
      const valid = await verifyPassword(body.password, user?.passwordHash ?? DUMMY_PASSWORD_HASH);
      if (!valid || !user) { res.status(401).json({ error: "Invalid email or password" }); return; }
      const token = newSessionToken();
      const expiresAt = new Date(Date.now() + options.sessionTtlHours * 60 * 60 * 1000).toISOString();
      db.prepare("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)")
        .run(digestToken(token), user.id, expiresAt);
      db.prepare("DELETE FROM sessions WHERE expires_at <= strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").run();
      res.cookie("saas_session", token, {
        httpOnly: true,
        secure: options.secureCookies,
        sameSite: "strict",
        path: "/",
        maxAge: options.sessionTtlHours * 60 * 60 * 1000,
      });
      audit(db, user.id, null, "auth.login", null);
      res.json({ user: { id: user.id, email: user.email } });
    } catch (error) { next(error); }
  });

  app.post("/auth/logout", auth, (req, res) => {
    const token = req.cookies?.saas_session as string;
    db.prepare("DELETE FROM sessions WHERE token_hash = ?").run(digestToken(token));
    audit(db, req.auth!.id, null, "auth.logout", null);
    res.clearCookie("saas_session", { httpOnly: true, secure: options.secureCookies, sameSite: "strict", path: "/" });
    res.status(204).end();
  });

  app.get("/auth/me", auth, (req, res) => {
    res.json({ user: req.auth, tenants: db.prepare(`SELECT t.id, t.name, t.slug, m.role
      FROM memberships m JOIN tenants t ON t.id = m.tenant_id WHERE m.user_id = ? ORDER BY t.name`).all(req.auth!.id) });
  });

  app.post("/users", auth, requirePlatformAdmin, async (req, res, next) => {
    try {
      const body = parseBody(userSchema, req, res);
      if (!body) return;
      const id = randomUUID();
      const passwordHash = await hashPassword(body.password);
      try {
        db.prepare("INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)")
          .run(id, body.email.toLowerCase(), passwordHash);
      } catch (error) {
        if (error instanceof Error && error.message.includes("UNIQUE")) { res.status(409).json({ error: "Email already exists" }); return; }
        throw error;
      }
      audit(db, req.auth!.id, null, "user.created", id, { email: body.email.toLowerCase() });
      res.status(201).json({ id, email: body.email.toLowerCase() });
    } catch (error) { next(error); }
  });

  app.get("/tenants", auth, (req, res) => {
    const tenants = req.auth!.platformAdmin
      ? db.prepare(`SELECT t.id, t.name, t.slug, t.created_at AS createdAt FROM tenants t ORDER BY t.name`).all()
      : db.prepare(`SELECT t.id, t.name, t.slug, m.role, t.created_at AS createdAt FROM tenants t
          JOIN memberships m ON m.tenant_id = t.id WHERE m.user_id = ? ORDER BY t.name`).all(req.auth!.id);
    res.json({ tenants });
  });

  app.post("/tenants", auth, requirePlatformAdmin, (req, res) => {
    const body = parseBody(tenantSchema, req, res);
    if (!body) return;
    const id = randomUUID();
    const create = (): void => {
      db.exec("BEGIN IMMEDIATE");
      try {
      db.prepare("INSERT INTO tenants (id, name, slug, created_by) VALUES (?, ?, ?, ?)").run(id, body.name, body.slug, req.auth!.id);
      db.prepare("INSERT INTO memberships (tenant_id, user_id, role) VALUES (?, ?, 'OWNER')").run(id, req.auth!.id);
      db.prepare("INSERT INTO subscriptions (tenant_id, plan, status, seats) VALUES (?, 'FREE', 'TRIAL', 3)").run(id);
      audit(db, req.auth!.id, id, "tenant.created", id, { slug: body.slug });
        db.exec("COMMIT");
      } catch (error) {
        db.exec("ROLLBACK");
        throw error;
      }
    };
    try { create(); }
    catch (error) {
      if (error instanceof Error && error.message.includes("UNIQUE")) { res.status(409).json({ error: "Tenant slug already exists" }); return; }
      throw error;
    }
    res.status(201).json({ tenant: { id, ...body }, subscription: { plan: "FREE", status: "TRIAL", seats: 3 } });
  });

  app.get("/tenants/:tenantId", auth, requireTenantRole(db, ["OWNER", "ADMIN", "BILLING", "MEMBER", "VIEWER"]), (req, res) => {
    const tenantId = routeParam(req, "tenantId");
    const tenant = db.prepare("SELECT id, name, slug, created_at AS createdAt FROM tenants WHERE id = ?").get(tenantId);
    if (!tenant) { res.status(404).json({ error: "Tenant not found" }); return; }
    res.json({ tenant });
  });

  app.get("/tenants/:tenantId/members", auth, requireTenantRole(db, ["OWNER", "ADMIN", "BILLING", "MEMBER", "VIEWER"]), (req, res) => {
    const members = db.prepare(`SELECT u.id, u.email, m.role, m.created_at AS createdAt FROM memberships m
      JOIN users u ON u.id = m.user_id WHERE m.tenant_id = ? ORDER BY u.email`).all(routeParam(req, "tenantId"));
    res.json({ members });
  });

  app.post("/tenants/:tenantId/members", auth, requireTenantRole(db, ["OWNER", "ADMIN"]), (req, res) => {
    const body = parseBody(memberSchema, req, res);
    if (!body) return;
    const user = db.prepare("SELECT id FROM users WHERE email = ? COLLATE NOCASE").get(body.email) as { id: string } | undefined;
    if (!user) { res.status(404).json({ error: "User not found; a platform administrator must create the account first" }); return; }
    try {
      db.prepare("INSERT INTO memberships (tenant_id, user_id, role) VALUES (?, ?, ?)")
        .run(routeParam(req, "tenantId"), user.id, body.role);
    } catch (error) {
      if (error instanceof Error && error.message.includes("UNIQUE")) { res.status(409).json({ error: "User is already a member" }); return; }
      throw error;
    }
    audit(db, req.auth!.id, routeParam(req, "tenantId"), "membership.created", user.id, { role: body.role });
    res.status(201).json({ userId: user.id, email: body.email.toLowerCase(), role: body.role });
  });

  app.patch("/tenants/:tenantId/members/:userId", auth, requireTenantRole(db, ["OWNER", "ADMIN"]), (req, res) => {
    const schema = z.object({ role: z.enum(["ADMIN", "BILLING", "MEMBER", "VIEWER"]) });
    const body = parseBody(schema, req, res);
    if (!body) return;
    const target = db.prepare("SELECT role FROM memberships WHERE tenant_id = ? AND user_id = ?")
      .get(routeParam(req, "tenantId"), routeParam(req, "userId")) as { role: TenantRole } | undefined;
    if (!target) { res.status(404).json({ error: "Membership not found" }); return; }
    if (target.role === "OWNER") { res.status(409).json({ error: "The tenant owner role cannot be changed through this endpoint" }); return; }
    db.prepare("UPDATE memberships SET role = ? WHERE tenant_id = ? AND user_id = ?")
      .run(body.role, routeParam(req, "tenantId"), routeParam(req, "userId"));
    audit(db, req.auth!.id, routeParam(req, "tenantId"), "membership.role_changed", routeParam(req, "userId"), { role: body.role });
    res.json({ userId: routeParam(req, "userId"), role: body.role });
  });

  app.get("/tenants/:tenantId/subscription", auth, requireTenantRole(db, ["OWNER", "ADMIN", "BILLING", "MEMBER", "VIEWER"]), (req, res) => {
    const subscription = db.prepare(`SELECT plan, status, seats, updated_at AS updatedAt FROM subscriptions WHERE tenant_id = ?`)
      .get(routeParam(req, "tenantId"));
    if (!subscription) { res.status(404).json({ error: "Subscription not found" }); return; }
    res.json({ subscription });
  });

  app.put("/tenants/:tenantId/subscription", auth, requireTenantRole(db, ["OWNER", "ADMIN", "BILLING"]), (req, res) => {
    const body = parseBody(subscriptionSchema, req, res);
    if (!body) return;
    db.prepare(`UPDATE subscriptions SET plan = ?, status = ?, seats = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE tenant_id = ?`)
      .run(body.plan, body.status, body.seats, routeParam(req, "tenantId"));
    audit(db, req.auth!.id, routeParam(req, "tenantId"), "subscription.updated", routeParam(req, "tenantId"), body);
    res.json({ subscription: body });
  });

  app.get("/tenants/:tenantId/audit", auth, requireTenantRole(db, ["OWNER", "ADMIN"]), (req, res) => {
    const events = db.prepare(`SELECT id, actor_user_id AS actorUserId, action, target_id AS targetId, details_json AS details,
      created_at AS createdAt FROM audit_events WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 100`)
      .all(routeParam(req, "tenantId")) as Array<{ details: string; [key: string]: unknown }>;
    res.json({ events: events.map(({ details, ...event }) => ({ ...event, details: JSON.parse(details) })) });
  });

  app.use((_req, res) => res.status(404).json({ error: "Route not found" }));

  const errors: ErrorRequestHandler = (error, _req, res, _next) => {
    process.stderr.write(`${JSON.stringify({ level: "error", event: "request_failed", name: error instanceof Error ? error.name : "UnknownError" })}\n`);
    if (res.headersSent) return;
    res.status(500).json({ error: "Internal server error" });
  };
  app.use(errors);
  return app;
}
