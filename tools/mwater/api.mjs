// Authenticated mWater v3 client, READ-ONLY. Same credential and login flow
// the MCP server uses.
//
// Since 25 September 2026 nothing in this repository writes to mWater: mWater
// allows writes only via the portal or MCP proposals. Every request goes
// through mwaterFetch(), which throws on any method other than GET except the
// login, POST /v3/clients, before anything is sent. The write helper and the
// scripts that used it are in tools/mwater/retired/.
import fs from "node:fs";

const ENV = "/home/bushp/mwater-mcp/.env";
const API = "https://api.mwater.co/v3";

function creds() {
  const t = fs.readFileSync(ENV, "utf8");
  const g = (k) => (t.match(new RegExp(`^${k}=(.*)$`, "m")) || [])[1]?.trim();
  const username = g("MWATER_USERNAME") || g("MWATER_USER");
  const password = g("MWATER_PASSWORD") || g("MWATER_PASS");
  if (!username || !password) throw new Error("no credentials in " + ENV);
  return { username, password };
}

/** The only way this client talks to mWater. GET anything; POST only to
 * /v3/clients (the login). Every other method or target throws. */
export async function mwaterFetch(url, init = {}) {
  const method = String(init.method ?? "GET").toUpperCase();
  const u = new URL(String(url));
  const isLogin = method === "POST" && u.pathname.replace(/\/+$/, "") === "/v3/clients";
  if (method !== "GET" && !isLogin) {
    throw new Error(`tools/mwater/api.mjs is read-only: refusing ${method} ${u.pathname}`);
  }
  return fetch(u, init);
}

let client = null;
async function login() {
  const r = await mwaterFetch(`${API}/clients`, {
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
    const r = await mwaterFetch(u);
    if (r.status === 401 && a === 0) { client = null; c = await login(); continue; }
    const t = await r.text();
    if (!r.ok) throw new Error(`GET /${pathname} HTTP ${r.status}: ${t.slice(0, 300)}`);
    try { return JSON.parse(t); } catch { return t; }
  }
}
