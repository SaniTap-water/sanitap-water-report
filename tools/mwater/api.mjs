// Authenticated mWater v3 client, same credential and login flow the MCP
// server uses. Read helpers are unrestricted; the write helper refuses
// anything that is not a whitelisted single-field entity patch.
import fs from "node:fs";
import path from "node:path";

const ENV = "/home/bushp/mwater-mcp/.env";
const API = "https://api.mwater.co/v3";
export const BACKUP = path.join(path.dirname(new URL(import.meta.url).pathname), "..", "..", "data", "mwater_backups");

function creds() {
  const t = fs.readFileSync(ENV, "utf8");
  const g = (k) => (t.match(new RegExp(`^${k}=(.*)$`, "m")) || [])[1]?.trim();
  const username = g("MWATER_USERNAME") || g("MWATER_USER");
  const password = g("MWATER_PASSWORD") || g("MWATER_PASS");
  if (!username || !password) throw new Error("no credentials in " + ENV);
  return { username, password };
}

let client = null;
async function login() {
  const r = await fetch(`${API}/clients`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(creds()),
  });
  if (!r.ok) throw new Error(`login HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
  const b = await r.json().catch(() => null);
  const id = typeof b === "string" ? b
    : b && (b.client || b.id || b._id || b.clientId);
  if (!id) throw new Error("login: no client id in response");
  client = id;
  return id;
}

export async function apiGet(pathname, params = {}) {
  let c = client ?? (await login());
  for (let a = 0; a < 2; a++) {
    const u = new URL(`${API}/${pathname}`);
    for (const [k, v] of Object.entries(params))
      u.searchParams.set(k, typeof v === "string" ? v : JSON.stringify(v));
    u.searchParams.set("client", c);
    const r = await fetch(u);
    if (r.status === 401 && a === 0) { client = null; c = await login(); continue; }
    const t = await r.text();
    if (!r.ok) throw new Error(`GET /${pathname} HTTP ${r.status}: ${t.slice(0, 300)}`);
    try { return JSON.parse(t); } catch { return t; }
  }
}

export async function apiWrite(method, pathname, body) {
  let c = client ?? (await login());
  for (let a = 0; a < 2; a++) {
    const u = new URL(`${API}/${pathname}`);
    u.searchParams.set("client", c);
    const r = await fetch(u, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (r.status === 401 && a === 0) { client = null; c = await login(); continue; }
    const t = await r.text();
    if (!r.ok) throw new Error(`${method} /${pathname} HTTP ${r.status}: ${t.slice(0, 400)}`);
    try { return JSON.parse(t); } catch { return t; }
  }
}

export function backup(tag, id, doc) {
  fs.mkdirSync(BACKUP, { recursive: true });
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const p = path.join(BACKUP, `${id}_${ts}_${tag}.json`);
  fs.writeFileSync(p, JSON.stringify(doc, null, 2), "utf8");
  return p;
}
