/* X boundaries and extraction. No network, storage, logging, or OCR. */
(function (root) {
  const postSelector = 'article[data-testid="tweet"]';
  const candidateSelector = `${postSelector}, [data-testid="trend"]`;
  const unique = values => [...new Set(values.map(value => value.replace(/\s+/gu, ' ').trim()).filter(Boolean))];
  function readable(node) {
    return node.nodeType !== Node.ELEMENT_NODE || (!node.hidden && !/^(SCRIPT|STYLE|NOSCRIPT)$/.test(node.nodeName));
  }
  function text(element, exclude = new Set()) {
    const parts = [];
    function visit(node) {
      if (exclude.has(node) || !readable(node)) return;
      if (node.nodeType === Node.TEXT_NODE) { parts.push(node.nodeValue); return; }
      const boundary = /^(DIV|P|BR|ARTICLE|LI|H[1-6])$/.test(node.nodeName);
      if (boundary) parts.push(' ');
      for (const child of node.childNodes) visit(child);
      if (boundary) parts.push(' ');
    }
    visit(element);
    return parts.join('').replace(/\s+/gu, ' ').trim();
  }
  function descriptions(post) {
    const alts = [], accessible = [];
    for (const image of post.querySelectorAll('img, [role="img"]')) {
      if (image.closest('[aria-hidden="true"], [hidden]')) continue;
      if (image.hasAttribute('alt')) alts.push(image.getAttribute('alt'));
      if (image.hasAttribute('aria-label')) accessible.push(image.getAttribute('aria-label'));
      for (const attribute of ['aria-labelledby', 'aria-describedby']) {
        for (const id of (image.getAttribute(attribute) || '').split(/\s+/u).filter(Boolean)) {
          const label = post.ownerDocument.getElementById(id);
          // Never follow a reference into another post, sidebar, or the search box.
          if (label && post.contains(label)) accessible.push(text(label));
        }
      }
    }
    return { imageAltText: unique(alts), accessibleImageText: unique(accessible) };
  }
  function quoteRoots(post) {
    const possible = [...post.querySelectorAll('[data-testid="quoteTweet"], [data-testid="quotedTweet"], article[data-testid="tweet"], div[role="link"]')]
      .filter(node => node.matches('[data-testid="quoteTweet"], [data-testid="quotedTweet"], article') ||
        (!node.closest('[data-testid="tweetText"], [data-testid="User-Name"]') && node.querySelector('[data-testid="tweetText"], [data-testid="User-Name"]')));
    return possible.filter(node => !possible.some(parent => parent !== node && parent.contains(node)));
  }
  function extract(post) {
    const quotes = quoteRoots(post);
    const authors = [...post.querySelectorAll('[data-testid="User-Name"]')].filter(node => !quotes.some(quote => quote.contains(node)));
    const authorText = unique(authors.map(node => text(node)));
    const quotedText = unique(quotes.map(node => text(node)));
    const outerText = text(post, new Set([...quotes, ...authors]));
    const images = descriptions(post);
    const segments = unique([outerText, ...authorText, ...quotedText, ...images.imageAltText, ...images.accessibleImageText]);
    return { outerText, authorText, quotedText, ...images, segments };
  }
  function findPost(element) {
    let post = element?.closest?.(postSelector);
    if (!post) return null;
    while (post.parentElement?.closest(postSelector)) post = post.parentElement.closest(postSelector);
    return post;
  }
  function identity(post) {
    const quotes = quoteRoots(post);
    const links = [...post.querySelectorAll('a[href*="/status/"]')].filter(link => !quotes.some(quote => quote.contains(link)));
    const link = links.find(link => link.querySelector('time')) || links[0];
    const id = link?.getAttribute('href')?.match(/\/status\/(\d+)/u)?.[1];
    return id || post.getAttribute('data-tweet-id') || post.getAttribute('data-item-id') || null;
  }
  root.NOpartisan.X = { postSelector, candidateSelector, extract, findPost, identity, text };
})(globalThis);
