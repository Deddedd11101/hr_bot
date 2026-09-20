/**
 * Проверка реестра дизайн-системы.
 *
 * Две вещи, которые нельзя проверить внутри самого реестра:
 *
 * 1. Заявленный `status` обязан совпадать с фактическим использованием
 *    компонента, посчитанным по импортам. Реестр не должен утверждать,
 *    что компонент работает в продукте, если его никто не импортирует.
 * 2. `sourceRef`, если он указан на локальный файл, обязан существовать.
 * 3. Имя записи-примитива обязано быть одним из реальных экспортов её
 *    `sourceRef`. Имена поддерживались руками, и 23 из 58 незаметно
 *    разошлись с кодом: `sonner.tsx` экспортирует `Toaster`,
 *    `chart.tsx` — `ChartContainer`, а записи назывались «Sonner» и «Chart».
 *
 * Запуск: node scripts/check-registry.mjs
 * Код возврата 1 при любой найденной проблеме — годится для CI.
 */

import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoDir = path.resolve(frontendDir, "..");
const srcDir = path.join(frontendDir, "src");
const uiDir = path.join(srcDir, "components", "ui");

/** Все .ts/.tsx под src — потребители компонентов. */
function collectSourceFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) {
      out.push(...collectSourceFiles(full));
    } else if (name.endsWith(".ts") || name.endsWith(".tsx")) {
      out.push(full);
    }
  }
  return out;
}

/** Фактический статус компонента кита по тому, кто его импортирует. */
function computeStatuses() {
  const files = collectSourceFiles(srcDir).map((file) => ({
    path: file.split(path.sep).join("/"),
    text: readFileSync(file, "utf8"),
  }));

  const statuses = new Map();
  for (const entry of readdirSync(uiDir)) {
    if (!entry.endsWith(".tsx")) continue;
    const name = entry.slice(0, -4);
    const pattern = new RegExp(`["']@/components/ui/${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}["']`);

    let inProduct = false;
    let inCatalog = false;
    let inKit = false;
    for (const file of files) {
      if (file.path.endsWith(`components/ui/${name}.tsx`)) continue;
      if (!pattern.test(file.text)) continue;
      if (file.path.includes("/components/ui/")) inKit = true;
      else if (file.path.includes("/design-system/")) inCatalog = true;
      else inProduct = true;
    }

    statuses.set(
      name,
      inProduct ? "product" : inCatalog ? "showcase" : inKit ? "internal" : "unused",
    );
  }
  return statuses;
}

/**
 * Имена, которые файл действительно экспортирует.
 *
 * Проверяем принадлежность, а не равенство одному символу: у составных
 * компонентов корней несколько (`ResizablePanelGroup` рядом с `ResizablePanel`),
 * и выбор между ними — вопрос вкуса. Выдуманное имя не пройдёт в любом случае.
 */
function exportedNames(file) {
  const text = readFileSync(file, "utf8");
  const names = new Set();

  for (const match of text.matchAll(/^export\s*\{([\s\S]*?)\}/gm)) {
    for (const raw of match[1].split(",")) {
      const name = raw.trim().replace(/\s+as\s+.*$/, "").replace(/^type\s+/, "");
      if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) names.add(name);
    }
  }
  for (const match of text.matchAll(/^export\s+(?:function|const|class)\s+([A-Za-z_][A-Za-z0-9_]*)/gm)) {
    names.add(match[1]);
  }
  return names;
}

/** Реестр — TypeScript, поэтому собираем его во временный CJS через esbuild. */
async function loadRegistry() {
  let esbuild;
  try {
    esbuild = await import("esbuild");
  } catch {
    console.error("esbuild не найден. Сначала: npm ci");
    process.exit(1);
  }

  const tmp = mkdtempSync(path.join(tmpdir(), "registry-"));
  const bundle = path.join(tmp, "registry.cjs");
  const cleanup = () => rmSync(tmp, { recursive: true, force: true });

  try {
    esbuild.buildSync({
      entryPoints: [path.join(srcDir, "design-system", "registry.ts")],
      bundle: true,
      format: "cjs",
      platform: "node",
      outfile: bundle,
      logLevel: "silent",
    });
  } catch (error) {
    cleanup();
    console.error("Не удалось собрать registry.ts: " + String(error.message));
    process.exit(1);
  }

  return { module: require(bundle), cleanup };
}

const { createRequire } = await import("node:module");
const require = createRequire(import.meta.url);

const { module: registry, cleanup } = await loadRegistry();
const problems = [];

for (const issue of registry.validateRegistry()) {
  problems.push(`${issue.entry}: ${issue.problem}`);
}

const actual = computeStatuses();

for (const entry of registry.CATALOG) {
  if (entry.status === "not-a-component") {
    if (entry.sourceRef && entry.sourceRef.includes("/components/ui/")) {
      problems.push(
        `${entry.id}: статус not-a-component, но sourceRef указывает на компонент кита`,
      );
    }
  } else {
    if (!entry.sourceRef) {
      problems.push(`${entry.id}: статус ${entry.status} требует sourceRef на компонент кита`);
      continue;
    }
    const name = path.basename(entry.sourceRef, ".tsx");
    const real = actual.get(name);
    if (!real) {
      problems.push(`${entry.id}: sourceRef ${entry.sourceRef} — такого компонента в ките нет`);
    } else if (real !== entry.status) {
      problems.push(
        `${entry.id}: заявлен статус "${entry.status}", фактически "${real}" (${name})`,
      );
    }
  }

  if (entry.sourceRef && !entry.sourceRef.startsWith("http")) {
    const full = path.join(repoDir, entry.sourceRef);
    if (!existsSync(full)) {
      problems.push(`${entry.id}: sourceRef ${entry.sourceRef} не существует`);
    } else if (entry.group === "primitives") {
      const names = exportedNames(full);
      if (!names.has(entry.title)) {
        const shown = [...names].slice(0, 6).join(", ");
        problems.push(
          `${entry.id}: имя "${entry.title}" не экспортируется из ${entry.sourceRef}` +
            (shown ? ` (там: ${shown}${names.size > 6 ? ", …" : ""})` : ""),
        );
      }
    }
  }
}

cleanup();

if (problems.length) {
  console.error(`Реестр: найдено проблем — ${problems.length}`);
  for (const problem of problems) console.error("  ✗ " + problem);
  process.exit(1);
}

console.log(`Реестр: ${registry.CATALOG.length} записей, проблем нет.`);
