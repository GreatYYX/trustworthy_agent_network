const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync(require.resolve("./demo-data.js"), "utf8");
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);

const data = context.window.GUARDRAIL_DEMO_DATA;
assert.ok(data, "demo data must load");
assert.deepEqual(Object.keys(data.models), ["sol", "opus"]);
assert.equal(data.demos.length, 4);

for (const demo of data.demos) {
  for (const model of Object.keys(data.models)) {
    assert.ok(Array.isArray(demo.cases[model]), `${demo.id}/${model} cases must exist`);
    assert.equal(demo.cases[model].length, 2, `${demo.id}/${model} must expose two cases`);
    for (const item of demo.cases[model]) {
      assert.ok(item.title && item.summary && item.outcome);
      assert.ok(Array.isArray(item.turns) && item.turns.length > 0);
    }
  }
  assert.ok(
    Number.isInteger(demo.boltedAttackIndex) && demo.boltedAttackIndex >= 0,
    `${demo.id} must select one recorded bolted-on attack`,
  );
  assert.equal(demo.bakedIn.length, 2, `${demo.id} must expose attack and valid TAN cases`);
  assert.equal(demo.bakedIn[0].outcome, "blocked", `${demo.id} baked-in attack must be denied`);
  assert.equal(demo.bakedIn[1].outcome, "allowed", `${demo.id} valid action must remain reachable`);
  for (const model of Object.keys(data.models)) {
    const comparison = [
      demo.cases[model][demo.boltedAttackIndex === 0 ? 1 : 0],
      demo.cases[model][demo.boltedAttackIndex],
      demo.bakedIn[0],
    ];
    assert.equal(comparison.length, 3);
    assert.ok(comparison[0], `${demo.id}/${model} effective bolted-on case must resolve`);
    assert.ok(comparison[1], `${demo.id}/${model} ineffective bolted-on case must resolve`);
    assert.ok(
      ["exploited", "partial"].includes(comparison[1].outcome),
      `${demo.id}/${model} second view must be the recorded bolted-on failure`,
    );
    assert.equal(comparison[2].outcome, "blocked");
  }
}

const html = fs.readFileSync(require.resolve("./demo.html"), "utf8");
const appSource = fs.readFileSync(require.resolve("./demo.js"), "utf8");
for (const model of Object.keys(data.models)) {
  assert.match(html, new RegExp(`data-model=["']${model}["']`));
}
assert.doesNotMatch(html, /data-model=["']tan["']/);
assert.match(html, /aria-label=["']Guardrail comparison["']/);
for (const label of ["Guardrail effective", "Guardrail ineffective", "Baked-in defense"]) {
  assert.match(appSource, new RegExp(label));
}

console.log("demo data: 2 models × 4 scenarios × 3 comparison views — PASS");
