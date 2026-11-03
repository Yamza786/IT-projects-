import assert from "node:assert/strict";
import { after, before, describe, it } from "node:test";
import { createApp } from "../dist/app.js";
import { migrate, openDatabase } from "../dist/database.js";

describe("marketplace API integration", () => {
  let db;
  let server;
  let baseUrl;
  let sellerCookie;
  let buyerCookies = [];
  let storeId;
  let productId;

  before(async () => {
    db = openDatabase(":memory:");
    migrate(db);
    migrate(db);
    const app = createApp({ db, sessionTtlHours: 1, secureCookies: false });
    server = app.listen(0, "127.0.0.1");
    await new Promise((resolve, reject) => {
      server.once("listening", resolve);
      server.once("error", reject);
    });
    baseUrl = `http://127.0.0.1:${server.address().port}`;
  });

  after(async () => {
    if (server) await new Promise((resolve) => server.close(resolve));
    db?.close();
  });

  async function call(path, { method = "GET", cookie, body, headers = {} } = {}) {
    const requestHeaders = { ...headers };
    if (body !== undefined) requestHeaders["content-type"] = "application/json";
    if (cookie) requestHeaders.cookie = cookie;
    const response = await fetch(`${baseUrl}${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    return { response, data: text ? JSON.parse(text) : null };
  }

  async function registerAndLogin(email) {
    const registered = await call("/auth/register", { method: "POST", body: { email, password: "long-test-password-123" } });
    assert.equal(registered.response.status, 201);
    const login = await call("/auth/login", { method: "POST", body: { email, password: "long-test-password-123" } });
    assert.equal(login.response.status, 200);
    return login.response.headers.get("set-cookie").split(";", 1)[0];
  }

  it("migrates repeatedly and protects seller operations by ownership", async () => {
    assert.equal(db.prepare("PRAGMA user_version").get().user_version, 1);
    assert.equal((await call("/cart")).response.status, 401);
    sellerCookie = await registerAndLogin("seller@example.test");
    const store = await call("/seller/stores", { method: "POST", cookie: sellerCookie, body: { name: "Fixture Goods" } });
    assert.equal(store.response.status, 201);
    storeId = store.data.store.id;
    const outsider = await registerAndLogin("buyer@example.test");
    const denied = await call(`/seller/stores/${storeId}/products`, { method: "POST", cookie: outsider, body: { name: "Wrong owner", priceCents: 500, inventory: 1 } });
    assert.equal(denied.response.status, 404);
    const product = await call(`/seller/stores/${storeId}/products`, { method: "POST", cookie: sellerCookie, body: { name: "Desk lamp", description: "Synthetic fixture", priceCents: 2499, inventory: 3 } });
    assert.equal(product.response.status, 201);
    productId = product.data.product.id;
    const ownerInventory = await call(`/seller/stores/${storeId}/products`, { cookie: sellerCookie });
    assert.equal(ownerInventory.response.status, 200);
    assert.equal(ownerInventory.data.products[0].inventory, 3);
    const outsiderInventory = await call(`/seller/stores/${storeId}/products`, { cookie: outsider });
    assert.equal(outsiderInventory.response.status, 404);
    buyerCookies = [outsider, await registerAndLogin("buyer-two@example.test")];
  });

  it("serves the browser storefront and compiled client bundle", async () => {
    const page = await fetch(`${baseUrl}/`);
    assert.equal(page.status, 200);
    assert.match(page.headers.get("content-security-policy"), /frame-ancestors 'none'/);
    assert.match(await page.text(), /Market Square/);
    const client = await fetch(`${baseUrl}/app.js`);
    assert.equal(client.status, 200);
    assert.match(await client.text(), /checkout-button/);
    const stylesheet = await fetch(`${baseUrl}/styles.css`);
    assert.equal(stylesheet.status, 200);
  });

  it("validates inputs and keeps public listings bounded", async () => {
    const invalid = await call("/auth/register", { method: "POST", body: { email: "invalid", password: "short" } });
    assert.equal(invalid.response.status, 400);
    const duplicate = await call("/auth/register", { method: "POST", body: { email: "SELLER@example.test", password: "long-test-password-123" } });
    assert.equal(duplicate.response.status, 409);
    const listing = await call("/products?limit=1000");
    assert.equal(listing.response.status, 400);
    const products = await call("/products");
    assert.equal(products.data.products[0].id, productId);
  });

  it("checks out atomically and returns the same order for an idempotent retry", async () => {
    const carts = await Promise.all(buyerCookies.map((cookie) => call("/cart/items", { method: "PUT", cookie, body: { productId, quantity: 2 } })));
    assert.deepEqual(carts.map(({ response }) => response.status), [200, 200]);
    const attempts = await Promise.all(buyerCookies.map((cookie, index) => call("/orders", {
      method: "POST", cookie, body: {}, headers: { "Idempotency-Key": `checkout-attempt-${index}-01` },
    })));
    assert.deepEqual(attempts.map(({ response }) => response.status).sort(), [201, 409]);
    const successfulIndex = attempts.findIndex(({ response }) => response.status === 201);
    const winningCookie = buyerCookies[successfulIndex];
    const firstOrder = attempts[successfulIndex].data.order;
    assert.equal(firstOrder.totalCents, 4998);
    assert.equal(firstOrder.paymentStatus, "SIMULATED_UNPAID");
    const retry = await call("/orders", {
      method: "POST", cookie: winningCookie, body: {}, headers: { "Idempotency-Key": `checkout-attempt-${successfulIndex}-01` },
    });
    assert.equal(retry.response.status, 200);
    assert.equal(retry.data.idempotentReplay, true);
    assert.equal(retry.data.order.id, firstOrder.id);
    const state = db.prepare("SELECT inventory FROM products WHERE id = ?").get(productId);
    assert.equal(state.inventory, 1);
    const sellerOrders = await call(`/seller/stores/${storeId}/orders`, { cookie: sellerCookie });
    assert.equal(sellerOrders.data.orders.length, 1);
  });
});
