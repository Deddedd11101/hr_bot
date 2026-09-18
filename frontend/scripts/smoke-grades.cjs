// Run only against an isolated local HRBot DB with a fixture employee.
// NODE_PATH must point to an environment providing Playwright (not a product dependency).
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const base = process.env.GRADE_SMOKE_URL || "http://127.0.0.1:8048";
if (!["127.0.0.1", "localhost"].includes(new URL(base).hostname)) throw new Error("Local isolated DB only");
const employeeId = process.env.GRADE_SMOKE_EMPLOYEE_ID || "1";
const out = process.env.GRADE_SMOKE_OUTPUT || path.resolve(__dirname, "../../artifacts/grades-ui");

(async () => {
  await fs.mkdir(out, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.GRADE_SMOKE_CHROMIUM });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.setDefaultTimeout(12000);
  const tag = Date.now().toString();
  async function choose(label, name) {
    await page.getByRole("combobox", { name: label, exact: true }).click();
    await page.getByRole("option", { name, exact: true }).click();
  }
  async function capture(name) {
    const tabs = page.getByRole("tab", { name: name === "catalog" ? "Матрица" : "Грейд", exact: true });
    const tabBox = await tabs.boundingBox();
    const content = name === "catalog" ? page.getByRole("combobox", { name: "Специализация", exact: true }) : page.getByRole("heading", { name: /Оценка от/ });
    const contentBox = await content.boundingBox();
    assert(tabBox.y < contentBox.y, "Tabs must be above content");
    for (const theme of ["light", "dark"]) {
      await page.evaluate(theme => { document.documentElement.classList.toggle("dark", theme === "dark"); document.documentElement.dataset.theme = theme; localStorage.setItem("theme", theme); }, theme);
      await page.screenshot({ path: path.join(out, `${name}-${theme}.png`), fullPage: true });
    }
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "Page overflows viewport");
  }
  try {
    await page.goto(`${base}/login`);
    await page.getByLabel("Логин", { exact: true }).fill("admin");
    await page.getByLabel("Пароль", { exact: true }).fill(process.env.GRADE_SMOKE_PASSWORD || "admin123");
    await page.getByRole("button", { name: "Войти", exact: true }).click();
    await page.waitForURL("**/app/dashboard");
    await page.goto(`${base}/app/grades`);
    await page.getByRole("tab", { name: "Специализации", exact: true }).click();
    await page.getByRole("button", { name: "Добавить", exact: true }).click();
    await page.getByLabel("Название", { exact: true }).fill(`Дизайн ${tag}`);
    await page.getByLabel("Код", { exact: true }).fill(`design-${tag}`);
    await page.getByRole("button", { name: "Сохранить", exact: true }).click();
    await page.getByRole("dialog").waitFor({ state: "hidden" });
    await page.getByRole("tab", { name: "Импорт", exact: true }).click();
    await choose("Специализация", `Дизайн ${tag}`);
    await page.getByLabel("Файл JSON", { exact: true }).setInputFiles(path.resolve(__dirname, "../../tools/data/grade-design-catalog.json"));
    await page.getByText("Файл прочитан", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Проверить импорт", exact: true }).click();
    await page.getByRole("button", { name: "Применить импорт", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Импортировать", exact: true }).click();
    await page.getByText("Каталог импортирован", { exact: true }).waitFor();
    await page.getByRole("tab", { name: "Матрица", exact: true }).click();
    await choose("Специализация", `Дизайн ${tag}`);
    const firstCell = page.getByRole("combobox").nth(1);
    await firstCell.click();
    await page.getByRole("option", { name: "2 · Умение", exact: true }).click();
    await page.getByRole("button", { name: "Сохранить матрицу", exact: true }).click();
    await page.getByText("Сохранено", { exact: true }).filter({ visible: true }).waitFor();
    await capture("catalog");
    await page.goto(`${base}/app/employees/${employeeId}`);
    await page.getByRole("tab", { name: "Грейд", exact: true }).click();
    await choose("Специализация", `Дизайн ${tag}`);
    await choose("Текущий грейд", "Junior");
    await choose("Цель", "Middle");
    await page.getByRole("button", { name: "Сохранить профиль", exact: true }).click();
    await page.getByText("Сохранено", { exact: true }).filter({ visible: true }).waitFor();
    await page.getByRole("button", { name: /Начать оценку|Продолжить оценку/ }).click();
    await page.getByRole("heading", { name: "Профиль навыков" }).waitFor();
    const levelButtons = page.locator('[data-slot="toggle-group-item"]');
    const selectedIndex = await levelButtons.nth(8).getAttribute("aria-pressed") === "true" ? 7 : 8;
    await levelButtons.nth(selectedIndex).click();
    await page.getByRole("tab", { name: "Профиль", exact: true }).click();
    await page.getByRole("tab", { name: "Грейд", exact: true }).click();
    assert.equal(await levelButtons.nth(selectedIndex).getAttribute("aria-pressed"), "true");
    await page.getByRole("button", { name: "Сохранить оценку", exact: true }).click();
    await page.getByText("Сохранено", { exact: true }).filter({ visible: true }).waitFor();
    assert(Number(await page.getByRole("progressbar").getAttribute("aria-valuenow")) > 0);
    await capture("assessment");
    await page.getByRole("button", { name: "Завершить оценку", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Завершить оценку", exact: true }).click();
    await page.getByText("Оценка завершена", { exact: true }).waitFor();
    assert(await levelButtons.first().isDisabled());
    await capture("final");
    await page.getByRole("button", { name: "К истории", exact: true }).click();
    await page.getByRole("button", { name: "Открыть оценку", exact: true }).first().waitFor();
    await page.goto(`${base}/app/design-system#record-with-tabs`);
    await page.locator("#record-with-tabs").waitFor();
    await page.locator("#record-with-tabs").screenshot({ path: path.join(out, "record-tabs.png") });
    await page.route("**/api/grades/workspace", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Тестовая ошибка" }) }));
    await page.goto(`${base}/app/grades`);
    await page.getByRole("alert").filter({ hasText: "Тестовая ошибка" }).waitFor();
    await page.unroute("**/api/grades/workspace");
    await page.getByRole("button", { name: "Повторить", exact: true }).click();
    await page.getByRole("tab", { name: "Матрица", exact: true }).waitFor();
    await page.getByRole("tab", { name: "Матрица", exact: true }).focus();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Enter");
    assert.equal(await page.getByRole("tab", { name: "Грейды", exact: true }).getAttribute("aria-selected"), "true");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ status: "passed", screenshots: out, browserErrors: errors }));
  } catch (error) {
    await page.screenshot({ path: path.join(out, "failure.png"), fullPage: true });
    console.error(await page.locator("body").innerText());
    throw error;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
