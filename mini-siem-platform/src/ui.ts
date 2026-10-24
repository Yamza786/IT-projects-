type AlertRecord = { id: string; rule_id: string; severity: string; title: string; event_ids: string[]; status: string; created_at: string };
type EventRecord = { id: string; occurred_at: string; received_at: string; source: string; actor: string; action: string; outcome: string; source_ip?: string };
type ErrorBody = { error?: { message?: string } };

let apiToken = "";
const byId = <T extends HTMLElement>(id: string): T => {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing UI element: ${id}`);
  return element as T;
};
const message = byId<HTMLParagraphElement>("message");

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${apiToken}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers, cache: "no-store" });
  const payload = await response.json() as T & ErrorBody;
  if (!response.ok) throw new Error(payload.error?.message ?? `Request failed (${response.status})`);
  return payload;
}

function addText(parent: HTMLElement, tag: string, value: string, className = ""): HTMLElement {
  const child = document.createElement(tag);
  child.textContent = value;
  if (className) child.className = className;
  parent.append(child);
  return child;
}

async function refresh(): Promise<void> {
  const status = byId<HTMLSelectElement>("status-filter").value;
  const [alertsResponse, eventsResponse] = await Promise.all([
    request<{ alerts: AlertRecord[] }>(`/api/v1/alerts?limit=100${status ? `&status=${encodeURIComponent(status)}` : ""}`),
    request<{ events: EventRecord[] }>("/api/v1/events?limit=100"),
  ]);
  byId<HTMLElement>("open-count").textContent = String(alertsResponse.alerts.filter((alert) => alert.status === "open").length);
  byId<HTMLElement>("event-count").textContent = String(eventsResponse.events.length);
  renderAlerts(alertsResponse.alerts);
  renderEvents(eventsResponse.events);
}

function renderAlerts(alerts: AlertRecord[]): void {
  const root = byId<HTMLDivElement>("alerts");
  root.replaceChildren();
  if (!alerts.length) { addText(root, "p", "No alerts match this filter.", "empty"); return; }
  for (const alert of alerts) {
    const card = document.createElement("article"); card.className = `alert-card ${alert.severity}`;
    addText(card, "h3", alert.title);
    addText(card, "div", `${alert.severity.toUpperCase()} · ${alert.rule_id} · ${alert.event_ids.length} event(s) · ${alert.status} · ${new Date(alert.created_at).toLocaleString()}`, "alert-meta");
    if (alert.status !== "resolved") {
      const actions = document.createElement("div"); actions.className = "alert-actions";
      if (alert.status === "open") addAction(actions, "Acknowledge", () => triage(alert.id, "acknowledged"));
      addAction(actions, "Resolve", () => triage(alert.id, "resolved"));
      card.append(actions);
    }
    root.append(card);
  }
}

function addAction(parent: HTMLElement, label: string, action: () => Promise<void>): void {
  const button = document.createElement("button"); button.type = "button"; button.className = "secondary"; button.textContent = label;
  button.addEventListener("click", () => { void action().catch(showError); }); parent.append(button);
}

async function triage(id: string, status: string): Promise<void> {
  await request(`/api/v1/alerts/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ status }) });
  await refresh();
  message.textContent = `Alert marked ${status}.`;
}

function renderEvents(events: EventRecord[]): void {
  const body = byId<HTMLTableSectionElement>("events"); body.replaceChildren();
  if (!events.length) { const row = body.insertRow(); const cell = row.insertCell(); cell.colSpan = 6; cell.className = "empty"; cell.textContent = "No events yet."; return; }
  for (const event of events) {
    const row = body.insertRow();
    [event.received_at, event.source, event.actor, event.action, event.outcome, event.source_ip ?? "—"].forEach((value) => { row.insertCell().textContent = value; });
  }
}

function showError(error: unknown): void { message.textContent = error instanceof Error ? error.message : "Unexpected error"; }

async function connect(): Promise<void> {
  apiToken = byId<HTMLInputElement>("token").value;
  if (!apiToken) { message.textContent = "Enter the API token."; return; }
  try {
    await refresh();
    byId<HTMLInputElement>("token").value = "";
    byId<HTMLButtonElement>("refresh").disabled = false;
    message.textContent = "Connected. The token is held in memory for this page only.";
  } catch (error) { apiToken = ""; showError(error); }
}

async function submitEvent(event: SubmitEvent): Promise<void> {
  event.preventDefault();
  const form = event.currentTarget as HTMLFormElement;
  const values = new FormData(form);
  const payload = {
    occurred_at: new Date().toISOString(),
    source: String(values.get("source") ?? ""),
    actor: String(values.get("actor") ?? ""),
    action: String(values.get("action") ?? ""),
    outcome: String(values.get("outcome") ?? ""),
    source_ip: String(values.get("source_ip") ?? ""),
    summary: "Synthetic analyst-console event",
  };
  try {
    const result = await request<{ alerts: AlertRecord[] }>("/api/v1/events", { method: "POST", body: JSON.stringify(payload) });
    await refresh();
    message.textContent = result.alerts.length ? `Event ingested; ${result.alerts.length} detection alert(s) created.` : "Event ingested; no rule matched.";
  } catch (error) { showError(error); }
}

async function checkHealth(): Promise<void> {
  try {
    const response = await fetch("/api/v1/health", { cache: "no-store" });
    if (!response.ok) throw new Error("Service unavailable");
    byId<HTMLElement>("health-dot").classList.add("online");
    byId<HTMLElement>("health-label").textContent = "Service online";
  } catch {
    byId<HTMLElement>("health-label").textContent = "Service offline";
  }
}

byId<HTMLButtonElement>("connect").addEventListener("click", () => { void connect(); });
byId<HTMLButtonElement>("refresh").addEventListener("click", () => { void refresh().catch(showError); });
byId<HTMLFormElement>("event-form").addEventListener("submit", (event) => { void submitEvent(event); });
byId<HTMLSelectElement>("status-filter").addEventListener("change", () => { if (apiToken) void refresh().catch(showError); });
void checkHealth();
