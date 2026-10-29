const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/employee-detail/adaptation-planner.tsx"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true,
} }).outputText;

// Exercise the real component's effects without a DOM or live API requests.
function mount(visible, hidden = false) {
  const effects = [], timers = new Map(), listeners = new Map(), requests = [];
  const react = { useState: value => [value, () => {}], useEffect: fn => effects.push(fn), createElement: () => null };
  const exports = {};
  const context = { exports, require: id => id === "react" ? { __esModule: true, default: react } : {},
    fetch: async url => { requests.push(url); return { ok: true, json: async () => ({ rows: [] }) }; },
    document: { hidden, addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name) },
    window: { setInterval: (fn, ms) => { timers.set(1, { fn, ms }); return 1; }, clearInterval: id => timers.delete(id),
      addEventListener: (name, fn) => listeners.set(name, fn), removeEventListener: name => listeners.delete(name) } };
  vm.runInNewContext(compiled, context);
  exports.AdaptationPlanner({ employeeId: 70, visible });
  return { effects, timers, listeners, requests, context };
}

test("inactive card tab does not install polling or focus listeners", () => {
  const state = mount(false);
  assert.equal(state.effects[1](), undefined);
  assert.equal(state.timers.size, 0);
  assert.equal(state.listeners.size, 0);
  assert.equal(state.requests.length, 0);
});

test("active tab refreshes immediately, avoids overlapping requests and cleans up", async () => {
  const state = mount(true);
  const cleanup = state.effects[1]();
  assert.equal(state.requests.length, 1);
  assert.equal(state.timers.get(1).ms, 15000);
  await state.listeners.get("focus")();
  assert.equal(state.requests.length, 1);
  await new Promise(resolve => setImmediate(resolve));
  await state.listeners.get("focus")();
  assert.equal(state.requests.length, 2);
  cleanup();
  assert.equal(state.timers.size, 0);
  assert.equal(state.listeners.size, 0);
});

test("hidden browser page waits for visibility before requesting", async () => {
  const state = mount(true, true);
  const cleanup = state.effects[1]();
  assert.equal(state.requests.length, 0);
  state.context.document.hidden = false;
  await state.listeners.get("visibilitychange")();
  assert.equal(state.requests.length, 1);
  cleanup();
});
