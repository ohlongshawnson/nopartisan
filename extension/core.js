/* Shared pure logic. Remote lists are data, never executable code. */
(function (root) {
  const DEFAULT_SOURCE = 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json';
  // A rule requires every `all` term and at least one `any` term in the same post.
  const contextualRules = [{ id: 'rule-1', all: ['Trump'], any: [
    'politics', 'political', 'president', 'presidential', 'election', 'elections',
    'campaign', 'vote', 'voting', 'voter', 'voters', 'democrat', 'democrats',
    'republican', 'republicans', 'immigration', 'deportation', 'deportations',
    'amnesty', 'white house', 'congress', 'senate', 'tariff', 'tariffs', 'policy',
    'government'
  ] }];
  const defaults = { enabled: true, showPlaceholders: true, custom: [], rules: contextualRules, source: DEFAULT_SOURCE, autoUpdate: false };
  const normalize = text => text.normalize('NFKC').toLocaleLowerCase('en-US').replace(/\s+/gu, ' ').trim();
  const pattern = term => new RegExp('(?<![\\p{L}\\p{N}_])' + normalize(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![\\p{L}\\p{N}_])', 'u');
  function validateRules(rules) {
    if (!Array.isArray(rules) || rules.length > 20) throw new Error('Use at most 20 contextual rules.');
    return rules.map((rule, index) => {
      if (!rule || !Array.isArray(rule.all) || rule.all.length !== 1 || !Array.isArray(rule.any) ||
          rule.any.length < 1 || rule.any.length > 30) throw new Error(`Invalid contextual rule on line ${index + 1}.`);
      const terms = [...rule.all, ...rule.any].map(term => {
        if (typeof term !== 'string' || !term.trim() || term.length > 120 || /[\p{Cc}]/u.test(term))
          throw new Error(`Invalid term in contextual rule on line ${index + 1}.`);
        return term.trim();
      });
      return { id: `rule-${index + 1}`, all: terms.slice(0, 1), any: terms.slice(1) };
    });
  }
  function parseRules(text) {
    return validateRules(text.split('\n').map(line => line.trim()).filter(Boolean).map((line, index) => {
      const parts = line.split('=>');
      if (parts.length !== 2) throw new Error(`Use "required => choice 1, choice 2" on line ${index + 1}.`);
      return { all: [parts[0]], any: parts[1].split(',') };
    }));
  }
  const formatRules = rules => validateRules(rules).map(rule => `${rule.all[0]} => ${rule.any.join(', ')}`).join('\n');
  function validate(data) {
    if (!data || data.schemaVersion !== 1 || typeof data.version !== 'string' || data.version.length > 100 ||
        !Array.isArray(data.keywords) || !data.keywords.length || data.keywords.length > 10000 ||
        data.keywords.some(k => typeof k !== 'string' || !k.trim() || k.length > 120 || /[\p{Cc}]/u.test(k))) {
      throw new Error('Invalid keyword list (schema 1; 1–10,000 phrases, each up to 120 characters).');
    }
    return { schemaVersion: 1, version: data.version, keywords: [...new Set(data.keywords.map(normalize))] };
  }
  function matcher(keywords) {
    const patterns = [...new Set(keywords.map(normalize).filter(Boolean))].map(pattern);
    return text => { const value = normalize(text); return patterns.some(p => p.test(value)); };
  }
  function ruleMatcher(rules) {
    const compiled = validateRules(rules).map(rule => ({ id: rule.id, all: rule.all.map(pattern), any: rule.any.map(pattern) }));
    return textOrSegments => {
      const segments = (Array.isArray(textOrSegments) ? textOrSegments : [textOrSegments]).map(normalize);
      const has = pattern => segments.some(segment => pattern.test(segment));
      return compiled.filter(rule => rule.all.every(has) && rule.any.some(has)).map(rule => rule.id);
    };
  }
  function sourceURL(value) {
    const url = new URL(value);
    if (url.origin !== 'https://raw.githubusercontent.com' || url.username || url.password || url.search || url.hash ||
        !/^\/[^/]+\/nopartisan\/[^/]+\/.+\.json$/.test(url.pathname)) throw new Error('Use an HTTPS raw.githubusercontent.com URL in a nopartisan repository.');
    return url.href;
  }
  root.NOpartisan = { DEFAULT_SOURCE, defaults, contextualRules, normalize, validate, validateRules, parseRules, formatRules, matcher, ruleMatcher, sourceURL };
})(globalThis);
