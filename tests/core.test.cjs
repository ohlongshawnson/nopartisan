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
test('contextual rules require all trigger terms and any one context term in either order', () => {
 const matches = core.ruleMatcher([{ id: 'test', all: ['Trump'], any: ['election', 'deportation'] }]);
 assert.deepEqual(matches('Trump discusses the election.'), ['rule-1']);
 assert.deepEqual(matches('Deportation plans from TRUMP.'), ['rule-1']);
 for (const text of ['Trump played a card.', 'An election is tomorrow.', 'Trumpets sounded during the election.']) {
  assert.deepEqual(matches(text), [], text);
 }
 const builtIn = core.ruleMatcher(core.contextualRules);
 assert.deepEqual(builtIn('Politics surrounding Trump.'), ['rule-1']);
 assert.deepEqual(builtIn('Trump and the election.'), ['rule-1']);
});
test('contextual rule text parses, formats, and rejects incomplete rules', () => {
 const rules = core.parseRules('Trump => politics, election\nvote => blue, red');
 assert.deepEqual(rules.map(rule => rule.id), ['rule-1', 'rule-2']);
 assert.equal(core.formatRules(rules), 'Trump => politics, election\nvote => blue, red');
 assert.deepEqual(core.parseRules(''), []);
 for (const invalid of ['Trump', 'Trump =>', '=> election', 'Trump => politics, ', 'Trump => politics => election']) {
  assert.throws(() => core.parseRules(invalid), invalid);
 }
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
