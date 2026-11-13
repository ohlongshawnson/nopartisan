const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
function fixture(callback) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'nopartisan-release-test-'));
  try {
    for (const name of ['extension', 'keywords']) fs.cpSync(name, path.join(root, name), { recursive: true });
    fs.mkdirSync(path.join(root, 'tools'));
    for (const name of ['package.json', 'package-lock.json', 'LICENSE', 'tools/package.py', 'tools/check_release.py']) fs.copyFileSync(name, path.join(root, name));
    const run = (...args) => spawnSync('python3', args, { cwd: root, encoding: 'utf8' });
    const build = run('tools/package.py'); assert.equal(build.status, 0, build.stderr);
    const version = JSON.parse(fs.readFileSync(path.join(root, 'package.json'))).version;
    return callback({ root, run, archive: path.join(root, 'dist', `nopartisan-${version}.zip`) });
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
}
function rejected(run, message) {
  const result = run('tools/check_release.py');
  assert.notEqual(result.status, 0); assert.match(result.stderr + result.stdout, message);
}
test('signing candidate guard validates reproducibility and rejects unsafe or inconsistent artifacts', async t => {
  await t.test('valid ZIP is reproducible and passes the guard', () => fixture(({ run, archive }) => {
    const before = fs.readFileSync(archive);
    const rebuilt = run('tools/package.py'); assert.equal(rebuilt.status, 0, rebuilt.stderr);
    assert.deepEqual(fs.readFileSync(archive), before);
    const checked = run('tools/check_release.py'); assert.equal(checked.status, 0, checked.stderr);
    assert.ok(fs.existsSync(`${archive}.sha256`));
  }));
  await t.test('diverging keyword copies are rejected', () => fixture(({ root, run }) => {
    const file = path.join(root, 'keywords/politics.json'); const data = JSON.parse(fs.readFileSync(file)); data.version = 'diverged';fs.writeFileSync(file, JSON.stringify(data));
    rejected(run, /published and bundled keyword files differ/);
  }));
  await t.test('removing a foundational term from both feeds is rejected', () => fixture(({ root, run }) => {
    for (const name of ['keywords/politics.json', 'extension/keywords.json']) {
      const file = path.join(root, name); const data = JSON.parse(fs.readFileSync(file));
      data.keywords = data.keywords.filter(term => term !== 'politics'); fs.writeFileSync(file, JSON.stringify(data));
    }
    rejected(run, /feed omits foundational vocabulary/);
  }));
  await t.test('an extra ZIP entry is rejected', () => fixture(({ run, archive }) => {
    const result = run('-c', 'import zipfile,sys; z=zipfile.ZipFile(sys.argv[1], "a"); z.writestr(".env", "TEST_ONLY=placeholder"); z.close()', archive);
    assert.equal(result.status, 0, result.stderr); rejected(run, /extra\/missing\/duplicate/);
  }));
  await t.test('unreviewed runtime files are rejected', () => fixture(({ root, run }) => {
    fs.writeFileSync(path.join(root, 'extension/.env'), 'TEST_ONLY=placeholder');rejected(run, /unreviewed or missing runtime files/);
  }));
  await t.test('credential-like strings are rejected without printing their value', () => fixture(({ root, run }) => {
    const file = path.join(root, 'extension/background.js');const fake = 'gh' + 'p_' + 'Z'.repeat(36);
    fs.appendFileSync(file, `\n// ${fake}\n`);
    assert.equal(run('tools/package.py').status, 0);
    const result = run('tools/check_release.py');assert.notEqual(result.status, 0);
    assert.match(result.stderr, /credential pattern/);assert.equal(result.stderr.includes(fake), false);
  }));
  await t.test('changing the permanent extension ID is rejected', () => fixture(({ root, run }) => {
    const file = path.join(root, 'extension/manifest.json');const data = JSON.parse(fs.readFileSync(file));data.browser_specific_settings.gecko.id = 'placeholder@example.org';fs.writeFileSync(file, JSON.stringify(data));
    rejected(run, /permanent Firefox ID changed/);
  }));
});
