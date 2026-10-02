/* Progressive enhancements: document links and content work without JavaScript. */
(() => {
  const searchDialog = document.querySelector('.search-dialog');
  const menuDialog = document.querySelector('.menu-dialog');
  const searchTrigger = document.querySelector('.search-trigger');
  const menuTrigger = document.querySelector('.menu-trigger');
  const input = document.querySelector('#search-input');
  const results = document.querySelector('.search-results');
  const status = document.querySelector('.search-status');
  let index;
  let loading;
  let searchVersion = 0;

  function show(dialog) {
    dialog.showModal();
    document.body.style.overflow = 'hidden';
  }
  for (const dialog of [searchDialog, menuDialog]) {
    dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); dialog.close(); }
    });
    dialog.addEventListener('close', () => { document.body.style.overflow = ''; });
    dialog.addEventListener('click', event => {
      if (event.target === dialog) {
        const rect = dialog.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
      }
    });
  }
  searchTrigger.hidden = false;
  menuTrigger.hidden = false;
  searchTrigger.addEventListener('click', () => { show(searchDialog); input.focus(); });
  menuTrigger.addEventListener('click', () => show(menuDialog));
  menuDialog.querySelectorAll('a').forEach(link => link.addEventListener('click', () => menuDialog.close()));
  document.addEventListener('keydown', event => {
    if ((event.key === '/' || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k')) &&
        !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) &&
        !document.activeElement.isContentEditable && !menuDialog.open && !searchDialog.open) {
      event.preventDefault(); show(searchDialog); input.focus();
    }
  });

  function highlighted(text, query) {
    const fragment = document.createDocumentFragment();
    const lower = text.toLowerCase();
    let position = 0;
    let match;
    while ((match = lower.indexOf(query, position)) !== -1) {
      fragment.append(document.createTextNode(text.slice(position, match)));
      const mark = document.createElement('mark');
      mark.textContent = text.slice(match, match + query.length);
      fragment.append(mark); position = match + query.length;
    }
    fragment.append(document.createTextNode(text.slice(position)));
    return fragment;
  }
  input.addEventListener('input', async () => {
    const version = ++searchVersion;
    const query = input.value.trim().toLowerCase();
    results.replaceChildren();
    if (!query) { status.textContent = '输入关键词，搜索全部章节与工单。'; return; }
    status.textContent = '正在查找…';
    try {
      if (!index) {
        loading ||= fetch(document.body.dataset.base + 'search.json').then(response => {
          if (!response.ok) throw new Error('Search index unavailable');
          return response.json();
        });
        index = await loading;
      }
    } catch {
      loading = undefined;
      if (version === searchVersion) status.textContent = '搜索索引暂时未能加载，请重新输入，或从目录进入章节。';
      return;
    }
    if (version !== searchVersion) return;
    const matches = index.map(section => {
      const title = (section.title + ' ' + section.heading).toLowerCase();
      const position = section.text.toLowerCase().indexOf(query);
      return { section, position, score: (title.includes(query) ? 3 : 0) + (position >= 0 ? 1 : 0) };
    }).filter(item => item.score).sort((a, b) => b.score - a.score);
    status.textContent = matches.length ? `找到 ${matches.length} 节内容${matches.length > 30 ? '，先显示最相关的 30 节' : ''}。` : '没有找到匹配内容。可以试试更短的关键词，例如「代理」或「SSH」。';
    for (const { section, position } of matches.slice(0, 30)) {
      const link = document.createElement('a'); link.className = 'search-result'; link.href = section.url;
      const chapter = document.createElement('small'); chapter.textContent = section.title;
      const heading = document.createElement('strong'); heading.append(highlighted(section.heading, query));
      const excerpt = document.createElement('p');
      const start = Math.max(0, position - 40);
      const snippet = (start ? '…' : '') + section.text.slice(start, start + 150) + (section.text.length > start + 150 ? '…' : '');
      excerpt.append(highlighted(snippet, query));
      link.append(chapter, heading, excerpt);
      link.addEventListener('click', () => searchDialog.close());
      results.append(link);
    }
  });

  document.querySelectorAll('.prose pre').forEach(pre => {
    const code = pre.querySelector('code');
    if (!code) return;
    pre.tabIndex = 0;
    const label = document.createElement('span'); label.className = 'code-language';
    label.textContent = [...code.classList].find(item => item.startsWith('language-'))?.replace('language-', '') || 'TEXT';
    const button = document.createElement('button'); button.type = 'button'; button.className = 'code-copy';
    button.textContent = '复制'; button.setAttribute('aria-label', '复制此代码块'); button.setAttribute('aria-live', 'polite');
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(code.textContent);
        button.textContent = '已复制 ✓';
      } catch {
        const range = document.createRange(); range.selectNodeContents(code);
        const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
        button.textContent = '已选中，请手动复制';
      }
      setTimeout(() => { button.textContent = '复制'; }, 2500);
    });
    pre.append(label, button);
  });
  const tocLinks = [...document.querySelectorAll('.page-toc a')];
  const headings = [...document.querySelectorAll('.prose h2[id], .prose h3[id]')];
  if (headings.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        tocLinks.forEach(link => link.classList.toggle('active', decodeURIComponent(link.hash.slice(1)) === entry.target.id));
      }
    }, { rootMargin: '-100px 0px -65% 0px' });
    headings.forEach(heading => observer.observe(heading));
  }
})();
