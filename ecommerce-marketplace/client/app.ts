type Product = { id: string; storeId: string; storeName: string; name: string; description: string; priceCents: number; inventory: number };
type CartItem = { productId: string; name: string; priceCents: number; quantity: number; lineTotalCents: number };
type Store = { id: string; name: string };
type SellerProduct = { id: string; name: string; priceCents: number; inventory: number; status: "ACTIVE" | "ARCHIVED" };

export {};

const message = document.querySelector<HTMLElement>("#message")!;
const productsElement = document.querySelector<HTMLElement>("#products")!;
const cartElement = document.querySelector<HTMLElement>("#cart-items")!;
const orderElement = document.querySelector<HTMLElement>("#orders")!;
const sellerProductsElement = document.querySelector<HTMLElement>("#seller-products")!;
const sellerOrdersElement = document.querySelector<HTMLElement>("#seller-orders")!;
const authPanel = document.querySelector<HTMLElement>("#auth-panel")!;
const sellerPanel = document.querySelector<HTMLElement>("#seller-panel")!;
const createStorePanel = document.querySelector<HTMLElement>("#create-store-panel")!;
const accountPanel = document.querySelector<HTMLElement>("#account-panel")!;
const logoutButton = document.querySelector<HTMLButtonElement>("#logout-button")!;
const accountLabel = document.querySelector<HTMLElement>("#account-label")!;
let currentStore: Store | null = null;

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body !== undefined) headers.set("content-type", "application/json");
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  if (response.status === 204) return undefined as T;
  const payload = await response.json() as { error?: string };
  if (!response.ok) throw new Error(payload.error ?? `Request failed (${response.status})`);
  return payload as T;
}

function reportError(error: unknown): void {
  message.textContent = error instanceof Error ? error.message : "Request failed. Try again.";
  message.className = "message error";
}

function reportSuccess(text: string): void {
  message.textContent = text;
  message.className = "message success";
}

function setHidden(element: HTMLElement, hidden: boolean): void {
  element.hidden = hidden;
}

function money(cents: number): string {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(cents / 100);
}

async function loadProducts(): Promise<void> {
  const result = await api<{ products: Product[] }>("/products?limit=50&offset=0");
  productsElement.replaceChildren();
  if (result.products.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No products are available yet. Create a seller store and add the first product.";
    productsElement.append(empty);
    return;
  }
  for (const product of result.products) {
    const card = document.createElement("article");
    card.className = "product-card";
    const store = document.createElement("p");
    store.className = "eyebrow";
    store.textContent = product.storeName;
    const title = document.createElement("h3");
    title.textContent = product.name;
    const description = document.createElement("p");
    description.className = "product-description";
    description.textContent = product.description || "No description provided.";
    const price = document.createElement("p");
    price.className = "price";
    price.textContent = money(product.priceCents);
    const stock = document.createElement("p");
    stock.className = "stock";
    stock.textContent = `${product.inventory} available`;
    const form = document.createElement("form");
    form.className = "add-to-cart-form";
    const quantityLabel = document.createElement("label");
    quantityLabel.textContent = "Quantity";
    const quantity = document.createElement("input");
    quantity.type = "number";
    quantity.min = "1";
    quantity.max = String(Math.min(100, product.inventory));
    quantity.value = "1";
    quantity.required = true;
    const add = document.createElement("button");
    add.type = "submit";
    add.textContent = "Set cart quantity";
    quantityLabel.append(quantity);
    form.append(quantityLabel, add);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await api("/cart/items", { method: "PUT", body: JSON.stringify({ productId: product.id, quantity: Number(quantity.value) }) });
        await refreshCart();
        reportSuccess(`${product.name} added to your cart.`);
      } catch (error) { reportError(error); }
    });
    card.append(store, title, description, price, stock, form);
    productsElement.append(card);
  }
}

async function refreshCart(): Promise<void> {
  try {
    const cart = await api<{ items: CartItem[]; totalCents: number }>("/cart");
    cartElement.replaceChildren();
    for (const item of cart.items) {
      const row = document.createElement("li");
      const detail = document.createElement("span");
      detail.textContent = `${item.name} × ${item.quantity} — ${money(item.lineTotalCents)}`;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "text-button";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${item.name} from cart`);
      remove.addEventListener("click", async () => {
        try {
          await api(`/cart/items/${encodeURIComponent(item.productId)}`, { method: "DELETE" });
          await refreshCart();
        } catch (error) { reportError(error); }
      });
      row.append(detail, remove);
      cartElement.append(row);
    }
    document.querySelector<HTMLElement>("#cart-total")!.textContent = money(cart.totalCents);
    const checkout = document.querySelector<HTMLButtonElement>("#checkout-button")!;
    checkout.disabled = cart.items.length === 0;
  } catch {
    cartElement.replaceChildren();
    document.querySelector<HTMLElement>("#cart-total")!.textContent = money(0);
    document.querySelector<HTMLButtonElement>("#checkout-button")!.disabled = true;
  }
}

async function refreshOrders(): Promise<void> {
  const result = await api<{ orders: Array<{ id: string; status: string; paymentStatus: string; totalCents: number; createdAt: string }> }>("/orders");
  orderElement.replaceChildren();
  for (const order of result.orders) {
    const item = document.createElement("li");
    item.textContent = `${new Date(order.createdAt).toLocaleString()} — ${money(order.totalCents)} — ${order.status} (${order.paymentStatus})`;
    orderElement.append(item);
  }
}

async function refreshStore(): Promise<void> {
  if (!currentStore) return;
  const [products, orders] = await Promise.all([
    api<{ products: SellerProduct[] }>(`/seller/stores/${encodeURIComponent(currentStore.id)}/products`),
    api<{ orders: Array<{ id: string; productName: string; quantity: number; unitPriceCents: number; paymentStatus: string }> }>(`/seller/stores/${encodeURIComponent(currentStore.id)}/orders`),
  ]);
  sellerProductsElement.replaceChildren();
  for (const product of products.products) {
    const row = document.createElement("li");
    const detail = document.createElement("span");
    detail.textContent = `${product.name} · ${money(product.priceCents)} · ${product.inventory} in stock · ${product.status}`;
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "text-button";
    edit.textContent = "Edit stock";
    edit.addEventListener("click", async () => {
      const nextInventory = window.prompt(`Set stock for ${product.name}`, String(product.inventory));
      if (nextInventory === null || !/^\d+$/.test(nextInventory)) return;
      try {
        await api(`/seller/stores/${encodeURIComponent(currentStore!.id)}/products/${encodeURIComponent(product.id)}`, {
          method: "PATCH", body: JSON.stringify({ inventory: Number(nextInventory), status: product.status }),
        });
        await refreshStore();
        await loadProducts();
      } catch (error) { reportError(error); }
    });
    const toggleStatus = document.createElement("button");
    toggleStatus.type = "button";
    toggleStatus.className = "text-button";
    toggleStatus.textContent = product.status === "ACTIVE" ? "Archive" : "Reactivate";
    toggleStatus.addEventListener("click", async () => {
      try {
        await api(`/seller/stores/${encodeURIComponent(currentStore!.id)}/products/${encodeURIComponent(product.id)}`, {
          method: "PATCH", body: JSON.stringify({ inventory: product.inventory, status: product.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE" }),
        });
        await refreshStore();
        await loadProducts();
      } catch (error) { reportError(error); }
    });
    row.append(detail, edit, toggleStatus);
    sellerProductsElement.append(row);
  }
  sellerOrdersElement.replaceChildren();
  for (const order of orders.orders) {
    const row = document.createElement("li");
    row.textContent = `${order.productName} × ${order.quantity} · ${money(order.unitPriceCents)} each · ${order.paymentStatus}`;
    sellerOrdersElement.append(row);
  }
}

async function refreshAccount(): Promise<void> {
  try {
    const result = await api<{ user: { email: string }; sellerStore: Store | null }>("/auth/me");
    currentStore = result.sellerStore;
    accountLabel.textContent = `Signed in as ${result.user.email}`;
    setHidden(authPanel, true);
    setHidden(accountPanel, false);
    setHidden(logoutButton, false);
    setHidden(createStorePanel, currentStore !== null);
    setHidden(sellerPanel, currentStore === null);
    if (currentStore) document.querySelector<HTMLElement>("#store-name")!.textContent = currentStore.name;
    await Promise.all([refreshCart(), refreshOrders(), currentStore ? refreshStore() : Promise.resolve()]);
  } catch {
    currentStore = null;
    setHidden(authPanel, false);
    setHidden(accountPanel, true);
    setHidden(logoutButton, true);
    setHidden(createStorePanel, true);
    setHidden(sellerPanel, true);
    await refreshCart();
  }
}

document.querySelector<HTMLFormElement>("#register-form")!.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget as HTMLFormElement);
  const email = String(form.get("email"));
  const password = String(form.get("password"));
  try {
    await api("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
    await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    await refreshAccount();
    reportSuccess("Your customer account is ready.");
  } catch (error) { reportError(error); }
});

document.querySelector<HTMLFormElement>("#login-form")!.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget as HTMLFormElement);
  try {
    await api("/auth/login", { method: "POST", body: JSON.stringify({ email: String(form.get("email")), password: String(form.get("password")) }) });
    await refreshAccount();
    reportSuccess("You are signed in.");
  } catch (error) { reportError(error); }
});

document.querySelector<HTMLFormElement>("#store-form")!.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget as HTMLFormElement);
  try {
    await api("/seller/stores", { method: "POST", body: JSON.stringify({ name: String(form.get("name")) }) });
    await refreshAccount();
    reportSuccess("Your seller store is ready.");
  } catch (error) { reportError(error); }
});

document.querySelector<HTMLFormElement>("#product-form")!.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentStore) return;
  const form = new FormData(event.currentTarget as HTMLFormElement);
  try {
    await api(`/seller/stores/${encodeURIComponent(currentStore.id)}/products`, {
      method: "POST",
      body: JSON.stringify({ name: String(form.get("name")), description: String(form.get("description")), priceCents: Math.round(Number(form.get("price")) * 100), inventory: Number(form.get("inventory")) }),
    });
    (event.currentTarget as HTMLFormElement).reset();
    await loadProducts();
    await refreshStore();
    reportSuccess("Product published to the catalog.");
  } catch (error) { reportError(error); }
});

document.querySelector<HTMLButtonElement>("#checkout-button")!.addEventListener("click", async () => {
  try {
    const order = await api<{ order: { id: string; totalCents: number; paymentStatus: string } }>("/orders", {
      method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({}),
    });
    reportSuccess(`Order ${order.order.id} placed for ${money(order.order.totalCents)}. Payment is not processed (${order.order.paymentStatus}).`);
    await Promise.all([refreshCart(), refreshOrders()]);
  } catch (error) { reportError(error); }
});

logoutButton.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    await refreshAccount();
    reportSuccess("You are signed out.");
  } catch (error) { reportError(error); }
});

document.querySelector<HTMLButtonElement>("#refresh-products")!.addEventListener("click", async () => {
  try { await loadProducts(); reportSuccess("Catalog refreshed."); }
  catch (error) { reportError(error); }
});

await loadProducts().catch(reportError);
await refreshAccount();
