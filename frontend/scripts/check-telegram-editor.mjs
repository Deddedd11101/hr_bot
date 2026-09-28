// Run with PLAYWRIGHT_MODULE pointing to an installed playwright package.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createServer } from "vite";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const harness = `
import React from 'react';
import { createRoot } from 'react-dom/client';
import { TelegramRichTextEditor } from '/src/components/ui/telegram-rich-text-editor';
import { TelegramMessageTools } from '/src/components/ui/telegram-message-tools';
import { buildEmployeeUpdatePayload } from '/src/employee-detail/helpers';
import '/src/index.css';
function App() {
  const [value, setValue] = React.useState('alpha beta');
  const [disabled, setDisabled] = React.useState(false);
  const insertRef = React.useRef(null);
  window.payloadForCheck = buildEmployeeUpdatePayload;
  return <><TelegramRichTextEditor value={value} onChange={setValue} insertRef={insertRef} disabled={disabled}/>
    <TelegramMessageTools tags={[{label:'Name tag',template:'{first_name}'}]} onInsertTag={text => insertRef.current?.(text)}/>
    <button onClick={() => setDisabled(!disabled)}>Toggle disabled</button>
    <button onClick={() => setValue('alpha beta')}>Reset</button>
    <output>{value}</output></>;
}
createRoot(document.getElementById('root')).render(<App/>);`;
const server = await createServer({
  base: "/",
  server: { host: "127.0.0.1", port: 0 },
  plugins: [{
    name: "editor-smoke-harness",
    resolveId(id) { if (id === "/__smoke.tsx") return id; },
    load(id) { if (id === "/__smoke.tsx") return harness; },
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!["/__smoke", "/__employee", "/__catalog"].includes(req.url)) return next();
        res.setHeader("Content-Type", "text/html");
        const body = req.url === "/__employee"
          ? '<div id="react-employee-edit-root" data-api-url="/api/employees/999" data-save-url="/api/employees/999"></div><script type="module" src="/src/employee-detail/main.tsx"></script>'
          : req.url === "/__catalog"
            ? '<div id="react-design-system-root"></div><script type="module" src="/src/design-system/main.tsx"></script>'
            : '<div id="root"></div><script type="module" src="/__smoke.tsx"></script>';
        res.end(await server.transformIndexHtml(req.url, `<html><head></head><body>${body}</body></html>`));
      });
    },
  }],
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_EXECUTABLE });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/__smoke`);
  const editor = page.locator(".tiptap");
  await editor.waitFor();
  async function select(from, to = from) {
    await editor.evaluate((element, [from, to]) => {
      element.focus();
      const text = element.querySelector("p").firstChild;
      const range = document.createRange();
      range.setStart(text, from);
      range.setEnd(text, to);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
      document.dispatchEvent(new Event("selectionchange"));
    }, [from, to]);
    await page.waitForTimeout(80);
  }
  async function checkValue(value) {
    await page.waitForFunction(value => document.querySelector("output").textContent === value, value);
  }
  async function reset() {
    await page.getByRole("button", { name: "Reset", exact: true }).click();
    await checkValue("alpha beta");
  }
  const picker = page.getByRole("button", { name: "Добавить эмоджи", exact: true });
  async function emoji() {
    await picker.click();
    await page.getByPlaceholder("Search").fill("grinning face");
    const button = page.locator('li[data-name="smileys_people"] button[data-unified="1f600"]').first();
    await button.waitFor();
    await button.click();
    await page.waitForFunction(() => document.activeElement?.classList.contains("tiptap"));
  }
  await select(6);
  await emoji();
  await checkValue("alpha 😀beta");
  await page.keyboard.type("X");
  await checkValue("alpha 😀Xbeta");
  await reset();
  await select(6, 10);
  await emoji();
  await checkValue("alpha 😀");
  await page.getByRole("button", { name: "Отменить", exact: true }).click();
  await checkValue("alpha beta");
  await select(6, 10);
  await page.getByRole("button", { name: "Name tag", exact: true }).focus();
  await page.keyboard.press("Enter");
  await checkValue("alpha {first_name}");
  await page.keyboard.type("X");
  await checkValue("alpha {first_name}X");
  await reset();
  await select(6);
  await page.getByRole("button", { name: "Name tag", exact: true }).click();
  await checkValue("alpha {first_name}beta");
  await reset();
  await select(6);
  await picker.focus();
  await page.keyboard.press("Enter");
  await page.locator(".EmojiPickerReact").waitFor();
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.activeElement?.classList.contains("tiptap"));
  await page.keyboard.type("X");
  await checkValue("alpha Xbeta");
  await page.getByRole("button", { name: "Toggle disabled" }).click();
  assert.equal(await picker.isDisabled(), true);
  await page.getByRole("button", { name: "Name tag", exact: true }).click();
  await checkValue("alpha Xbeta");
  await page.getByRole("button", { name: "Toggle disabled" }).click();
  await page.setViewportSize({ width: 320, height: 640 });
  await picker.click();
  const box = await page.getByRole("dialog", { name: "Выбор эмоджи" }).boundingBox();
  assert.ok(box.x >= 0 && box.x + box.width <= 320, JSON.stringify(box));
  await page.keyboard.press("Escape");
  const payloads = await page.evaluate(() => [
    window.payloadForCheck({ full_name: "Surname Name", first_name: "Stored", ipr_url: "https://example.com/ipr" }),
    window.payloadForCheck({ full_name: "Surname Name", first_name: "Stored", ipr_url: "" }),
    window.payloadForCheck({ full_name: "Surname Name", first_name: "Stored" }),
  ]);
  assert.equal(payloads[0].first_name, "Stored");
  assert.equal(payloads[0].ipr_url, "https://example.com/ipr");
  assert.equal(payloads[1].ipr_url, "");
  assert.equal(Object.hasOwn(payloads[2], "ipr_url"), false);
  await page.setViewportSize({ width: 1280, height: 900 });
  const origin = new URL(page.url()).origin;
  await page.goto(`${origin}/__catalog#telegram-rich-text-editor`);
  await page.locator('#telegram-rich-text-editor').getByRole('button', { name: 'Добавить эмоджи', exact: true }).waitFor();
  const employee = { id: 999, full_name: "Surname Name", first_name: "Stored", employee_role: "employee", adaptation_tasks_url: "", adaptation_feedback_url: "", ipr_url: "https://example.com/old" };
  const fixture = { employee, meta: { is_candidate: false }, files: [], scheduled_launches: [], manual_launch_history: [], options: {} };
  const saves = [];
  await page.route('**/api/**', async route => {
    const request = route.request();
    if (request.url().endsWith('/api/settings/workspace')) return route.fulfill({ json: {} });
    assert.ok(request.url().endsWith('/api/employees/999'), request.url());
    if (request.method() === 'POST') {
      const saved = request.postDataJSON();
      saves.push(saved);
      Object.assign(employee, saved);
    }
    await route.fulfill({ json: fixture });
  });
  await page.goto(`${origin}/__employee`);
  const ipr = page.getByLabel('Ссылка на ИПР', { exact: true });
  await ipr.waitFor();
  assert.equal(await ipr.inputValue(), employee.ipr_url);
  assert.equal(await page.locator('input[name="first_name"]').count(), 0);
  for (const value of ['https://example.com/new', '']) {
    await ipr.fill(value);
    const response = page.waitForResponse(response => response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Сохранить', exact: true }).click();
    await response;
    assert.equal(saves.at(-1).ipr_url, value);
    assert.equal(saves.at(-1).first_name, 'Stored');
  }
  assert.equal(await page.getByRole('button', { name: 'Добавить эмоджи', exact: true }).count(), 1);
  assert.deepEqual(errors, []);
  console.log("PASS: emoji caret/replacement/undo/continued typing; tag mouse/keyboard selection; Escape focus; disabled; 320px picker; catalog and employee page; preserved first_name; IPR set/clear/omit payloads and mock POST; no page errors.");
} finally {
  await browser?.close();
  await server.close();
}
