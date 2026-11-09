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
