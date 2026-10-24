import { randomUUID } from "node:crypto";
import cookieParser from "cookie-parser";
import express, { type ErrorRequestHandler, type Request, type Response } from "express";
import helmet from "helmet";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { requireAuth, requireStoreOwner } from "./auth.js";
import type { Database } from "./database.js";
import { createSessionToken, digestSessionToken, hashPassword, verifyPassword } from "./security.js";

const registrationSchema = z.object({ email: z.string().trim().email().max(254), password: z.string().min(12).max(256) }).strict();
const loginSchema = z.object({ email: z.string().trim().email().max(254), password: z.string().min(1).max(256) }).strict();
const storeSchema = z.object({ name: z.string().trim().min(2).max(100) }).strict();
const productSchema = z.object({ name: z.string().trim().min(2).max(120), description: z.string().max(2000).default(""), priceCents: z.number().int().min(1).max(100000000), inventory: z.number().int().min(0).max(1000000) }).strict();
const cartSchema = z.object({ productId: z.string().uuid(), quantity: z.number().int().min(1).max(100) }).strict();
const checkoutSchema = z.object({}).strict();
const DUMMY_HASH = `scrypt$16384$8$1$${"00".repeat(16)}$${"00".repeat(64)}`;

interface AppOptions {
  db: Database;
  sessionTtlHours: number;
  secureCookies: boolean;
}

function parseBody<T>(schema: z.ZodType<T>, request: Request, response: Response): T | undefined {
  const parsed = schema.safeParse(request.body);
  if (!parsed.success) {
    response.status(400).json({ error: "Invalid request", issues: parsed.error.issues.map(({ path, message }) => ({ path, message })) });
    return undefined;
  }
  return parsed.data;
}

function routeParam(request: Request, key: string): string {
  const value = request.params[key];
  return typeof value === "string" ? value : Array.isArray(value) ? value[0] ?? "" : "";
}

function audit(db: Database, actorId: string, action: string, targetId: string, details: unknown = {}): void {
  db.prepare("INSERT INTO audit_events (id, actor_user_id, action, target_id, details_json) VALUES (?, ?, ?, ?, ?)")
    .run(randomUUID(), actorId, action, targetId, JSON.stringify(details));
}

export function createApp(options: AppOptions) {
  const { db } = options;
  const app = express();
  app.disable("x-powered-by");
  app.use(helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        baseUri: ["'self'"],
        connectSrc: ["'self'"],
        formAction: ["'self'"],
        frameAncestors: ["'none'"],
        imgSrc: ["'self'", "data:"],
        objectSrc: ["'none'"],
        scriptSrc: ["'self'"],
        scriptSrcAttr: ["'none'"],
        styleSrc: ["'self'"],
        upgradeInsecureRequests: null,
      },
    },
  }));
  app.use(express.json({ limit: "32kb", strict: true }));
  app.use(cookieParser());
  app.use(express.static(resolve(dirname(fileURLToPath(import.meta.url)), "public"), { fallthrough: true, index: "index.html", maxAge: "1h" }));
  app.use((request, response, next) => {
    const startedAt = Date.now();
    response.on("finish", () => process.stdout.write(`${JSON.stringify({ level: "info", event: "http_request", method: request.method, path: request.path, status: response.statusCode, duration_ms: Date.now() - startedAt })}\n`));
    next();
  });

  const auth = requireAuth(db);
  app.get("/health", (_request, response) => response.json({ status: "ok" }));

  app.post("/auth/register", async (request, response, next) => {
    try {
      const body = parseBody(registrationSchema, request, response);
      if (!body) return;
      const id = randomUUID();
      try {
        db.prepare("INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)")
          .run(id, body.email.toLowerCase(), await hashPassword(body.password));
      } catch (error) {
        if (error instanceof Error && error.message.includes("UNIQUE")) { response.status(409).json({ error: "Account already exists" }); return; }
        throw error;
      }
      audit(db, id, "customer.registered", id);
      response.status(201).json({ id, email: body.email.toLowerCase() });
    } catch (error) { next(error); }
  });

  app.post("/auth/login", async (request, response, next) => {
    try {
      const body = parseBody(loginSchema, request, response);
      if (!body) return;
      const user = db.prepare("SELECT id, email, password_hash AS passwordHash FROM users WHERE email = ? COLLATE NOCASE")
        .get(body.email) as { id: string; email: string; passwordHash: string } | undefined;
      const valid = await verifyPassword(body.password, user?.passwordHash ?? DUMMY_HASH);
      if (!valid || !user) { response.status(401).json({ error: "Invalid email or password" }); return; }
      const token = createSessionToken();
      const expiresAt = new Date(Date.now() + options.sessionTtlHours * 60 * 60 * 1000).toISOString();
      db.prepare("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)").run(digestSessionToken(token), user.id, expiresAt);
      db.prepare("DELETE FROM sessions WHERE expires_at <= strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").run();
      response.cookie("marketplace_session", token, { httpOnly: true, secure: options.secureCookies, sameSite: "strict", path: "/", maxAge: options.sessionTtlHours * 60 * 60 * 1000 });
      audit(db, user.id, "auth.login", user.id);
      response.json({ user: { id: user.id, email: user.email } });
    } catch (error) { next(error); }
  });

  app.post("/auth/logout", auth, (request, response) => {
    const token = request.cookies.marketplace_session as string;
    db.prepare("DELETE FROM sessions WHERE token_hash = ?").run(digestSessionToken(token));
    audit(db, request.marketplaceUser!.id, "auth.logout", request.marketplaceUser!.id);
    response.clearCookie("marketplace_session", { httpOnly: true, secure: options.secureCookies, sameSite: "strict", path: "/" });
    response.status(204).end();
  });

  app.get("/auth/me", auth, (request, response) => {
    const store = db.prepare("SELECT id, name FROM stores WHERE owner_user_id = ?").get(request.marketplaceUser!.id);
    response.json({ user: request.marketplaceUser, sellerStore: store ?? null });
  });

  app.post("/seller/stores", auth, (request, response) => {
    const body = parseBody(storeSchema, request, response);
    if (!body) return;
    const id = randomUUID();
    try {
      db.prepare("INSERT INTO stores (id, owner_user_id, name) VALUES (?, ?, ?)").run(id, request.marketplaceUser!.id, body.name);
    } catch (error) {
      if (error instanceof Error && error.message.includes("UNIQUE")) { response.status(409).json({ error: "This account already owns a store" }); return; }
      throw error;
    }
    audit(db, request.marketplaceUser!.id, "store.created", id);
    response.status(201).json({ store: { id, name: body.name } });
  });

  app.get("/seller/stores/:storeId/products", auth, requireStoreOwner(db), (request, response) => {
    const products = db.prepare(`SELECT id, name, description, price_cents AS priceCents, inventory, status,
      created_at AS createdAt FROM products WHERE store_id = ? ORDER BY created_at DESC LIMIT 100`)
      .all(routeParam(request, "storeId"));
    response.json({ products });
  });

  app.post("/seller/stores/:storeId/products", auth, requireStoreOwner(db), (request, response) => {
    const body = parseBody(productSchema, request, response);
    if (!body) return;
    const storeId = routeParam(request, "storeId");
    const id = randomUUID();
    db.prepare("INSERT INTO products (id, store_id, name, description, price_cents, inventory) VALUES (?, ?, ?, ?, ?, ?)")
      .run(id, storeId, body.name, body.description, body.priceCents, body.inventory);
    audit(db, request.marketplaceUser!.id, "product.created", id, { storeId });
    response.status(201).json({ product: { id, storeId, ...body, status: "ACTIVE" } });
  });

  app.patch("/seller/stores/:storeId/products/:productId", auth, requireStoreOwner(db), (request, response) => {
    const body = parseBody(z.object({ inventory: z.number().int().min(0).max(1000000), status: z.enum(["ACTIVE", "ARCHIVED"]) }).strict(), request, response);
    if (!body) return;
    const storeId = routeParam(request, "storeId");
    const productId = routeParam(request, "productId");
    const result = db.prepare(`UPDATE products SET inventory = ?, status = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
      WHERE id = ? AND store_id = ?`).run(body.inventory, body.status, productId, storeId);
    if (result.changes === 0) { response.status(404).json({ error: "Product not found" }); return; }
    audit(db, request.marketplaceUser!.id, "product.inventory_or_status_changed", productId, body);
    response.json({ product: { id: productId, ...body } });
  });

  app.get("/products", (request, response) => {
    const parsed = z.object({ limit: z.coerce.number().int().min(1).max(100).default(30), offset: z.coerce.number().int().min(0).max(100000).default(0) }).safeParse(request.query);
    if (!parsed.success) { response.status(400).json({ error: "Invalid pagination" }); return; }
    const products = db.prepare(`SELECT p.id, p.store_id AS storeId, s.name AS storeName, p.name, p.description,
      p.price_cents AS priceCents, p.inventory, p.created_at AS createdAt
      FROM products p JOIN stores s ON s.id = p.store_id
      WHERE p.status = 'ACTIVE' AND p.inventory > 0 ORDER BY p.created_at DESC, p.id LIMIT ? OFFSET ?`)
      .all(parsed.data.limit, parsed.data.offset);
    response.json({ products });
  });

  app.get("/cart", auth, (request, response) => {
    const items = db.prepare(`SELECT p.id AS productId, p.name, p.price_cents AS priceCents, c.quantity,
      (p.price_cents * c.quantity) AS lineTotalCents FROM cart_items c JOIN products p ON p.id = c.product_id
      WHERE c.user_id = ? ORDER BY p.name`).all(request.marketplaceUser!.id);
    const total = (items as Array<{ lineTotalCents: number }>).reduce((sum, item) => sum + item.lineTotalCents, 0);
    response.json({ items, totalCents: total });
  });

  app.put("/cart/items", auth, (request, response) => {
    const body = parseBody(cartSchema, request, response);
    if (!body) return;
    const product = db.prepare("SELECT inventory FROM products WHERE id = ? AND status = 'ACTIVE'").get(body.productId) as { inventory: number } | undefined;
    if (!product) { response.status(404).json({ error: "Available product not found" }); return; }
    if (product.inventory < body.quantity) { response.status(409).json({ error: "Requested quantity exceeds available inventory" }); return; }
    const existingItem = db.prepare("SELECT 1 FROM cart_items WHERE user_id = ? AND product_id = ?").get(request.marketplaceUser!.id, body.productId);
    const itemCount = db.prepare("SELECT COUNT(*) AS count FROM cart_items WHERE user_id = ?").get(request.marketplaceUser!.id) as { count: number };
    if (!existingItem && itemCount.count >= 100) { response.status(409).json({ error: "Cart is limited to 100 distinct products" }); return; }
    db.prepare(`INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)
      ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = excluded.quantity, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')`)
      .run(request.marketplaceUser!.id, body.productId, body.quantity);
    response.status(200).json({ productId: body.productId, quantity: body.quantity });
  });

  app.delete("/cart/items/:productId", auth, (request, response) => {
    db.prepare("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?").run(request.marketplaceUser!.id, routeParam(request, "productId"));
    response.status(204).end();
  });

  app.post("/orders", auth, (request, response) => {
    if (!parseBody(checkoutSchema, request, response)) return;
    const idempotencyKey = request.get("Idempotency-Key") ?? "";
    if (!/^[A-Za-z0-9_-]{16,80}$/.test(idempotencyKey)) { response.status(400).json({ error: "Idempotency-Key header must be 16-80 letters, digits, underscores or hyphens" }); return; }
    const userId = request.marketplaceUser!.id;
    db.exec("BEGIN IMMEDIATE");
    try {
      const existing = db.prepare("SELECT id, status, payment_status AS paymentStatus, total_cents AS totalCents FROM orders WHERE user_id = ? AND idempotency_key = ?")
        .get(userId, idempotencyKey) as { id: string; status: string; paymentStatus: string; totalCents: number } | undefined;
      if (existing) {
        db.exec("COMMIT");
        response.status(200).json({ order: existing, idempotentReplay: true });
        return;
      }
      const items = db.prepare(`SELECT c.product_id AS productId, c.quantity, p.name, p.store_id AS storeId,
        p.price_cents AS priceCents, p.inventory FROM cart_items c JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ? AND p.status = 'ACTIVE' ORDER BY c.product_id`).all(userId) as Array<{ productId: string; quantity: number; name: string; storeId: string; priceCents: number; inventory: number }>;
      if (items.length === 0) { db.exec("ROLLBACK"); response.status(409).json({ error: "Cart has no available items" }); return; }
      const unavailable = items.find((item) => item.quantity > item.inventory);
      if (unavailable) { db.exec("ROLLBACK"); response.status(409).json({ error: "Cart quantity exceeds current inventory", productId: unavailable.productId }); return; }
      const totalCents = items.reduce((sum, item) => sum + item.priceCents * item.quantity, 0);
      if (!Number.isSafeInteger(totalCents)) { db.exec("ROLLBACK"); response.status(409).json({ error: "Order total exceeds supported range" }); return; }
      const orderId = randomUUID();
      db.prepare("INSERT INTO orders (id, user_id, idempotency_key, status, payment_status, total_cents) VALUES (?, ?, ?, 'PLACED', 'SIMULATED_UNPAID', ?)")
        .run(orderId, userId, idempotencyKey, totalCents);
      for (const item of items) {
        const updated = db.prepare("UPDATE products SET inventory = inventory - ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ? AND status = 'ACTIVE' AND inventory >= ?")
          .run(item.quantity, item.productId, item.quantity);
        if (updated.changes !== 1) throw new Error("Inventory changed during checkout");
        db.prepare("INSERT INTO order_items (order_id, product_id, product_name, store_id, quantity, unit_price_cents) VALUES (?, ?, ?, ?, ?, ?)")
          .run(orderId, item.productId, item.name, item.storeId, item.quantity, item.priceCents);
      }
      db.prepare("DELETE FROM cart_items WHERE user_id = ?").run(userId);
      audit(db, userId, "order.placed", orderId, { totalCents, itemCount: items.length });
      db.exec("COMMIT");
      response.status(201).json({ order: { id: orderId, status: "PLACED", paymentStatus: "SIMULATED_UNPAID", totalCents }, idempotentReplay: false });
    } catch (error) {
      db.exec("ROLLBACK");
      throw error;
    }
  });

  app.get("/orders", auth, (request, response) => {
    const orders = db.prepare(`SELECT id, status, payment_status AS paymentStatus, total_cents AS totalCents, created_at AS createdAt
      FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 100`).all(request.marketplaceUser!.id);
    response.json({ orders });
  });

  app.get("/seller/stores/:storeId/orders", auth, requireStoreOwner(db), (request, response) => {
    const storeId = routeParam(request, "storeId");
    const orders = db.prepare(`SELECT o.id, o.status, o.payment_status AS paymentStatus, oi.product_name AS productName,
      oi.quantity, oi.unit_price_cents AS unitPriceCents, o.created_at AS createdAt
      FROM order_items oi JOIN orders o ON o.id = oi.order_id WHERE oi.store_id = ?
      ORDER BY o.created_at DESC LIMIT 100`).all(storeId);
    response.json({ orders });
  });

  app.use((_request, response) => response.status(404).json({ error: "Route not found" }));
  const errors: ErrorRequestHandler = (error, _request, response, _next) => {
    process.stderr.write(`${JSON.stringify({ level: "error", event: "request_failed", name: error instanceof Error ? error.name : "UnknownError" })}\n`);
    if (!response.headersSent) response.status(500).json({ error: "Internal server error" });
  };
  app.use(errors);
  return app;
}
