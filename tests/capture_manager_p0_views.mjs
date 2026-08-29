import fs from "node:fs/promises";
import path from "node:path";

const [, , debugPort, outputDir, baseUrl, managerPhone, managerPassword, adminUser, adminPassword] = process.argv;
if (!debugPort || !outputDir || !baseUrl) {
  throw new Error("Usage: node capture_manager_p0_views.mjs <debug-port> <output-dir> <base-url> ...");
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const pages = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json();
const target = pages.find((item) => item.type === "page");
if (!target) throw new Error("No Chrome page target found");

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener("open", resolve, { once: true });
  ws.addEventListener("error", reject, { once: true });
});

let nextId = 1;
const pending = new Map();
ws.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const waiter = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) waiter.reject(new Error(message.error.message));
  else waiter.resolve(message.result || {});
});

function call(method, params = {}) {
  const id = nextId++;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function evaluate(expression) {
  return call("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
}

async function capture(filename) {
  await evaluate("window.scrollTo(0, 0)");
  await sleep(400);
  const shot = await call("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: true,
  });
  await fs.writeFile(path.join(outputDir, filename), Buffer.from(shot.data, "base64"));
}

async function navigate(url) {
  await call("Page.navigate", { url });
  await sleep(1800);
}

await fs.mkdir(outputDir, { recursive: true });
await call("Page.enable");
await call("Runtime.enable");
await call("Emulation.setDeviceMetricsOverride", {
  width: 1440,
  height: 1100,
  deviceScaleFactor: 1,
  mobile: false,
});

await navigate(`${baseUrl}/manager`);
await capture("01-manager-login.png");
await evaluate(`(() => {
  const form = document.querySelector('#manager-login-form');
  form.elements.phone.value = ${JSON.stringify(managerPhone)};
  form.elements.password.value = ${JSON.stringify(managerPassword)};
  form.requestSubmit();
})()`);
await sleep(1800);
await capture("02-manager-workbench.png");
await evaluate("document.querySelector('#manager-project-list')?.scrollIntoView({block: 'start'})");
await sleep(500);
const managerProjectShot = await call("Page.captureScreenshot", {
  format: "png",
  captureBeyondViewport: false,
  fromSurface: true,
});
await fs.writeFile(path.join(outputDir, "02b-manager-projects.png"), Buffer.from(managerProjectShot.data, "base64"));

await navigate(`${baseUrl}/admin`);
await evaluate(`(() => {
  const form = document.querySelector('#admin-login-form');
  form.elements.username.value = ${JSON.stringify(adminUser)};
  form.elements.password.value = ${JSON.stringify(adminPassword)};
  form.requestSubmit();
})()`);
await sleep(2200);
await capture("03-admin-manager-p0.png");
await evaluate("document.querySelector('[data-admin-manager]')?.click()");
await sleep(500);
await evaluate("document.querySelector('#admin-manager-detail')?.scrollIntoView({block: 'center'})");
await sleep(400);
const managerReviewShot = await call("Page.captureScreenshot", {
  format: "png",
  captureBeyondViewport: false,
  fromSurface: true,
});
await fs.writeFile(path.join(outputDir, "04-admin-manager-review.png"), Buffer.from(managerReviewShot.data, "base64"));

await evaluate("document.querySelector('[data-admin-manager-project]')?.click()");
await sleep(900);
await evaluate("document.querySelector('#admin-manager-project-detail')?.scrollIntoView({block: 'start'})");
await sleep(400);
const projectDetailShot = await call("Page.captureScreenshot", {
  format: "png",
  captureBeyondViewport: false,
  fromSurface: true,
});
await fs.writeFile(path.join(outputDir, "05-admin-project-detail.png"), Buffer.from(projectDetailShot.data, "base64"));

ws.close();
