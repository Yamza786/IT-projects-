import type { NextFunction, Request, Response } from "express";
import type { Database } from "./database.js";
import { digestToken } from "./security.js";

export type TenantRole = "OWNER" | "ADMIN" | "BILLING" | "MEMBER" | "VIEWER";
export interface AuthUser { id: string; email: string; platformAdmin: boolean }

declare global {
  namespace Express {
    interface Request { auth?: AuthUser }
  }
}

export function requireAuth(db: Database) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const token = req.cookies?.saas_session;
    if (typeof token !== "string" || token.length < 40) {
      res.status(401).json({ error: "Authentication required" });
      return;
    }
    const row = db.prepare(`SELECT u.id, u.email, u.platform_admin AS platformAdmin
      FROM sessions s JOIN users u ON u.id = s.user_id
      WHERE s.token_hash = ? AND s.expires_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now')`)
      .get(digestToken(token)) as { id: string; email: string; platformAdmin: number } | undefined;
    if (!row) {
      res.status(401).json({ error: "Session is invalid or expired" });
      return;
    }
    req.auth = { id: row.id, email: row.email, platformAdmin: Boolean(row.platformAdmin) };
    next();
  };
}

export function requirePlatformAdmin(req: Request, res: Response, next: NextFunction): void {
  if (!req.auth?.platformAdmin) {
    res.status(403).json({ error: "Platform administrator role required" });
    return;
  }
  next();
}

export function requireTenantRole(db: Database, allowed: TenantRole[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const tenantValue = req.params.tenantId;
    const tenantId = typeof tenantValue === "string" ? tenantValue : Array.isArray(tenantValue) ? tenantValue[0] ?? "" : "";
    if (!db.prepare("SELECT 1 FROM tenants WHERE id = ?").get(tenantId)) {
      res.status(404).json({ error: "Tenant not found" });
      return;
    }
    if (req.auth?.platformAdmin) { next(); return; }
    const membership = db.prepare("SELECT role FROM memberships WHERE tenant_id = ? AND user_id = ?")
      .get(tenantId, req.auth!.id) as { role: TenantRole } | undefined;
    if (!membership || !allowed.includes(membership.role)) {
      res.status(403).json({ error: "Insufficient tenant permissions" });
      return;
    }
    next();
  };
}
