import type { NextFunction, Request, Response } from "express";
import { digestSessionToken } from "./security.js";
import type { Database } from "./database.js";

declare global {
  namespace Express {
    interface Request { marketplaceUser?: { id: string; email: string } }
  }
}

export function requireAuth(db: Database) {
  return (request: Request, response: Response, next: NextFunction): void => {
    const token = request.cookies?.marketplace_session;
    if (typeof token !== "string" || token.length < 40 || token.length > 60) {
      response.status(401).json({ error: "Authentication required" });
      return;
    }
    const user = db.prepare(`SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id
      WHERE s.token_hash = ? AND s.expires_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now')`).get(digestSessionToken(token)) as { id: string; email: string } | undefined;
    if (!user) { response.status(401).json({ error: "Authentication required" }); return; }
    request.marketplaceUser = user;
    next();
  };
}

export function requireStoreOwner(db: Database) {
  return (request: Request, response: Response, next: NextFunction): void => {
    const routeStoreId = request.params.storeId;
    const storeId = typeof routeStoreId === "string" ? routeStoreId : Array.isArray(routeStoreId) ? routeStoreId[0] : undefined;
    if (!storeId) { response.status(404).json({ error: "Store not found" }); return; }
    const userId = request.marketplaceUser?.id;
    if (!userId) { response.status(401).json({ error: "Authentication required" }); return; }
    const store = db.prepare("SELECT id FROM stores WHERE id = ? AND owner_user_id = ?")
      .get(storeId, userId);
    if (!store) { response.status(404).json({ error: "Store not found" }); return; }
    next();
  };
}
