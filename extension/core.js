/* Shared pure logic. Remote lists are data, never executable code. */
(function (root) {
  const DEFAULT_SOURCE = 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json';
  const defaults = { enabled: true, showPlaceholders: true, custom: [], source: DEFAULT_SOURCE, autoUpdate: false };
  const sites = { X: 'https://x.com/*', Reddit: 'https://www.reddit.com/*', Facebook: 'https://www.facebook.com/*' };
  const normalize = text => text.normalize('NFKC').toLocaleLowerCase('en-US').replace(/\s+/gu, ' ').trim();
  function validate(data) {
    if (!data || data.schemaVersion !== 1 || typeof data.version !== 'string' || data.version.length > 100 ||
        !Array.isArray(data.keywords) || !data.keywords.length || data.keywords.length > 10000 ||
        data.keywords.some(k => typeof k !== 'string' || !k.trim() || k.length > 120 || /[\p{Cc}]/u.test(k))) {
      throw new Error('Invalid keyword list (schema 1; 1–10,000 phrases, each up to 120 characters).');
    }
    return { schemaVersion: 1, version: data.version, keywords: [...new Set(data.keywords.map(normalize))] };
  }
  function matcher(keywords) {
    const patterns = [...new Set(keywords.map(normalize).filter(Boolean))].map(k =>
      new RegExp('(?<![\\p{L}\\p{N}_])' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![\\p{L}\\p{N}_])', 'u'));
    return text => { const value = normalize(text); return patterns.some(p => p.test(value)); };
  }
  function sourceURL(value) {
    const url = new URL(value);
    if (url.origin !== 'https://raw.githubusercontent.com' || url.username || url.password || url.search || url.hash ||
        !/^\/[^/]+\/nopartisan\/[^/]+\/.+\.json$/.test(url.pathname)) throw new Error('Use an HTTPS raw.githubusercontent.com URL in a nopartisan repository.');
    return url.href;
  }
  root.NOpartisan = { DEFAULT_SOURCE, defaults, sites, normalize, validate, matcher, sourceURL };
})(globalThis);
