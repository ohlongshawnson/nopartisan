/* Shared pure logic. Remote lists are data, never executable code. */
(function (root) {
  const DEFAULT_SOURCE = 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json';
  const defaults = { enabled: true, showPlaceholders: true, custom: [], source: DEFAULT_SOURCE, autoUpdate: false };
  // A rule requires every `all` term and at least one `any` term in the same post.
  const contextualRules = [{ id: 'trump-political-context', all: ['Trump'], any: [
    'politics', 'political', 'president', 'presidential', 'election', 'elections',
    'campaign', 'vote', 'voting', 'voter', 'voters', 'democrat', 'democrats',
    'republican', 'republicans', 'immigration', 'deportation', 'deportations',
    'amnesty', 'white house', 'congress', 'senate', 'tariff', 'tariffs', 'policy',
    'government'
  ] }];
  const normalize = text => text.normalize('NFKC').toLocaleLowerCase('en-US').replace(/\s+/gu, ' ').trim();
  const pattern = term => new RegExp('(?<![\\p{L}\\p{N}_])' + normalize(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![\\p{L}\\p{N}_])', 'u');
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
    const compiled = rules.map(rule => ({ id: rule.id, all: rule.all.map(pattern), any: rule.any.map(pattern) }));
    return text => {
      const value = normalize(text);
      return compiled.filter(rule => rule.all.every(p => p.test(value)) && rule.any.some(p => p.test(value))).map(rule => rule.id);
    };
  }
  function sourceURL(value) {
    const url = new URL(value);
    if (url.origin !== 'https://raw.githubusercontent.com' || url.username || url.password || url.search || url.hash ||
        !/^\/[^/]+\/nopartisan\/[^/]+\/.+\.json$/.test(url.pathname)) throw new Error('Use an HTTPS raw.githubusercontent.com URL in a nopartisan repository.');
    return url.href;
  }
  root.NOpartisan = { DEFAULT_SOURCE, defaults, contextualRules, normalize, validate, matcher, ruleMatcher, sourceURL };
})(globalThis);
