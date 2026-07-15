const PUBLIC_PATHS = new Set(["stats", "public/demands", "match", "intents", "progress/query"]);
const DEFAULT_API_BASE = "https://technexus-demo.onrender.com";

async function forward(request: Request) {
  const incoming = new URL(request.url);
  const path = (incoming.searchParams.get("path") || "").replace(/^\/+/, "");
  if (!PUBLIC_PATHS.has(path)) return Response.json({ ok: false, message: "不允许访问该接口" }, { status: 403 });

  const target = new URL(`/api/${path}`, process.env.TECHNEXUS_API_BASE_URL || DEFAULT_API_BASE);
  incoming.searchParams.forEach((value, key) => { if (key !== "path") target.searchParams.append(key, value); });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), path === "match" ? 85000 : 95000);
  try {
    const headers = new Headers();
    headers.set("Accept", "application/json");
    if (request.method !== "GET") headers.set("Content-Type", "application/json");
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" ? undefined : await request.text(),
      signal: controller.signal,
    });
    const body = await response.text();
    return new Response(body || JSON.stringify({ ok: response.ok }), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") || "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json({ ok: false, message: "需求服务正在唤醒或响应超时，请稍后重试。" }, { status: 504 });
  } finally { clearTimeout(timer); }
}

export async function GET(request: Request) { return forward(request); }
export async function POST(request: Request) { return forward(request); }
