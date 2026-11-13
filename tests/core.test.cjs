const { test } = require('node:test');
const assert = require('node:assert/strict');
require('../extension/core.js');
const core = global.NOpartisan;
test('case, whitespace, Unicode boundaries, and literal punctuation', () => {
 const matches = core.matcher(['Republican Party', 'MAGA', 'C++', 'élection']);
 assert.equal(matches('The REPUBLICAN\n PARTY platform'), true);
 assert.equal(matches('magazine'), false);
 assert.equal(matches('MAGA2026'), false);
 assert.equal(matches('éMAGA'), false);
 assert.equal(matches('#MAGA!'), true);
 assert.equal(matches('Learning C++ today'), true);
 assert.equal(matches('une élection.'), true);
});
test('malformed or oversized remote lists rejected', () => {
 for (const data of [null, {}, {schemaVersion:1,version:'v',keywords:['']}, {schemaVersion:1,version:'v',keywords:['a'.repeat(121)]}]) assert.throws(() => core.validate(data));
 assert.deepEqual(core.validate({schemaVersion:1,version:'v',keywords:['MAGA','maga']}).keywords,['maga']);
});
test('only explicit GitHub nopartisan JSON sources accepted', () => {
 assert.equal(core.DEFAULT_SOURCE, 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json');
 assert.equal(core.defaults.source, core.DEFAULT_SOURCE);
 assert.equal(core.sourceURL('https://raw.githubusercontent.com/owner/nopartisan/main/keywords/politics.json'), 'https://raw.githubusercontent.com/owner/nopartisan/main/keywords/politics.json');
 for (const url of ['http://raw.githubusercontent.com/a/nopartisan/main/x.json','https://evil.test/a/nopartisan/main/x.json','https://raw.githubusercontent.com/a/other/main/x.json','https://raw.githubusercontent.com/a/nopartisan/main/x.json?q=1']) assert.throws(() => core.sourceURL(url));
});

test('website guidance requests exactly the manifest filtering origins', () => {
 const vm = require('node:vm'); const fs = require('node:fs');
 const ctx = vm.createContext({ URL });
 vm.runInContext(fs.readFileSync('extension/core.js', 'utf8'), ctx);
 const manifest = JSON.parse(fs.readFileSync('extension/manifest.json', 'utf8'));
 assert.deepEqual(Object.values(ctx.NOpartisan.sites).sort(), manifest.host_permissions.slice().sort());
 assert.equal(Object.values(ctx.NOpartisan.sites).includes('https://raw.githubusercontent.com/*'), false);
 const bundled = JSON.parse(fs.readFileSync('extension/keywords.json', 'utf8'));
 assert.equal(ctx.NOpartisan.matcher(bundled.keywords)('Mike Lee spoke today'), true);
 assert.equal(ctx.NOpartisan.matcher(bundled.keywords)('Mark Levin spoke today'), false, 'Reported phrase is a coverage gap in the shipped list');
});
