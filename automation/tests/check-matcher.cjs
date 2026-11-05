/* Run the actual extension matcher against a complete proposed/downloaded list. */
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { performance } = require('node:perf_hooks');
require('../../extension/core.js');
const core = globalThis.NOpartisan;
const expanded = core.validate(JSON.parse(fs.readFileSync(process.argv[2], 'utf8')));
const baseline = core.validate(JSON.parse(fs.readFileSync(process.argv[3], 'utf8')));
const cases = JSON.parse(fs.readFileSync(__dirname + '/matcher-cases.json', 'utf8'));
const matches = core.matcher(expanded.keywords);
for (const text of cases.positive) assert.equal(matches(text), true, 'Political miss: ' + text);
for (const text of cases.negative) assert.equal(matches(text), false, 'Nonpolitical false positive: ' + text);
const sample = ('Gardeners planted tomatoes and watered the flowers. Music and sports filled the weekend. ' +
                '生活 أخبار café météo. ').repeat(18);
const corpus = [sample, ...cases.positive, ...cases.negative];
function measure(list) {
  const started = performance.now();
  const match = core.matcher(list.keywords);
  const compileMs = performance.now() - started;
  for (let i = 0; i < 100; i++) match(corpus[i % corpus.length]);
  const durations = [];
  for (let i = 0; i < 1600; i++) {
    const text = i % 2 === 0 ? sample : corpus[i % corpus.length];
    const before = performance.now();
    match(text);
    durations.push(performance.now() - before);
  }
  durations.sort((a, b) => a - b);
  const before = performance.now();
  match(sample.repeat(5));
  return { keywords: list.keywords.length, compileMs, medianMs: durations[800], p95Ms: durations[1520],
           maxMs: durations[1599], longBenignMs: performance.now() - before };
}
const report = { node: process.version, schemaVersion: expanded.schemaVersion, version: expanded.version,
  politicalCases: cases.positive.length, nonpoliticalCases: cases.negative.length,
  benchmarkIterations: 1600, benignSampleCharacters: sample.length,
  baseline: measure(baseline), expanded: measure(expanded),
  limitation: 'Node/V8 on this server, using unchanged extension/core.js; not a Firefox UI benchmark.' };
assert.ok(report.expanded.p95Ms < 25, 'p95 matching exceeded the 25 ms/post server benchmark budget');
console.log(JSON.stringify(report, null, 2));
