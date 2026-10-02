#!/usr/bin/env node
// Render the small, deliberate subset used by docs/diagrams/*.excalidraw.
// SVG generation uses Node built-ins; PNG export uses an existing local browser.
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const directory = join(root, 'docs/diagrams');
const options = { png: false };
for (let i = 2; i < process.argv.length; i++) {
  const arg = process.argv[i];
  if (arg === '--png') options.png = true;
  else if (arg === '--playwright-module' || arg === '--browser') {
    if (!process.argv[i + 1]) throw new Error(`${arg} needs a path`);
    options[arg.slice(2)] = resolve(process.argv[++i]);
  } else throw new Error(`Unknown argument: ${arg}`);
}
if (options.png && (!options['playwright-module'] || !options.browser)) {
  throw new Error('--png requires --playwright-module and --browser; nothing is downloaded');
}

const escape = value => String(value).replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'
}[c]));
const dash = style => style === 'dashed' ? '10 7' : style === 'dotted' ? '3 6' : '';
const semantic = [];
const rendered = [];
for (const filename of (await readdir(directory)).filter(p => p.endsWith('.excalidraw')).sort()) {
  const source = JSON.parse(await readFile(join(directory, filename), 'utf8'));
  const meta = source.elements.find(e => e.id === 'title')?.customData?.guide;
  if (!meta) throw new Error(`${filename}: missing title.customData.guide metadata`);
  const elements = source.elements.filter(e => !e.isDeleted);
  const ids = new Set(elements.map(e => e.id));
  if (ids.size !== elements.length) throw new Error(`${filename}: duplicate IDs`);
  const chunks = [];
  for (const e of elements) {
    if (e.angle !== 0) throw new Error(`${filename}: rotation is outside this renderer's subset`);
    const stroke = escape(e.strokeColor);
    const fill = e.backgroundColor === 'transparent' ? 'none' : escape(e.backgroundColor);
    const line = `stroke="${stroke}" stroke-width="${e.strokeWidth}" stroke-dasharray="${dash(e.strokeStyle)}"`;
    if (e.type === 'rectangle') {
      chunks.push(`<rect id="${escape(e.id)}" x="${e.x}" y="${e.y}" width="${e.width}" height="${e.height}" rx="${e.roundness ? 16 : 0}" fill="${fill}" ${line}/>`);
    } else if (e.type === 'text') {
      const anchor = e.textAlign === 'center' ? 'middle' : e.textAlign === 'right' ? 'end' : 'start';
      const x = e.x + (anchor === 'middle' ? e.width / 2 : anchor === 'end' ? e.width : 0);
      const lineHeight = e.fontSize * (e.lineHeight ?? 1.25);
      const lines = e.text.split('\n').map((s, i) => `<tspan x="${x}" y="${e.y + e.fontSize + i * lineHeight}"${i === 0 && e.customData?.boldFirstLine ? ' font-weight="700"' : ''}>${escape(s)}</tspan>`).join('');
      chunks.push(`<text id="${escape(e.id)}" data-container-id="${escape(e.containerId || '')}" fill="${stroke}" font-size="${e.fontSize}" font-weight="${e.customData?.weight || 400}" text-anchor="${anchor}">${lines}</text>`);
    } else if (e.type === 'arrow' || e.type === 'line') {
      for (const binding of [e.startBinding, e.endBinding]) {
        if (binding && !ids.has(binding.elementId)) throw new Error(`${filename}: missing arrow binding`);
      }
      if (![null, 'arrow'].includes(e.startArrowhead) || ![null, 'arrow'].includes(e.endArrowhead)) {
        throw new Error(`${filename}: unsupported arrowhead`);
      }
      const marker = `head-${e.id}`;
      const points = e.points.map(([x, y]) => `${e.x + x},${e.y + y}`).join(' ');
      chunks.push(`<defs><marker id="${escape(marker)}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto-start-reverse" markerUnits="strokeWidth"><path d="M1 1 L7 4 L1 7" fill="none" stroke="${stroke}" stroke-width="1.4"/></marker></defs>`);
      chunks.push(`<polyline id="${escape(e.id)}" points="${points}" fill="none" ${line} stroke-linejoin="round" stroke-linecap="round"${e.startArrowhead ? ` marker-start="url(#${marker})"` : ''}${e.endArrowhead ? ` marker-end="url(#${marker})"` : ''}/>`);
    } else throw new Error(`${filename}: unsupported element ${e.type}`);
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${meta.width}" height="${meta.height}" viewBox="0 0 ${meta.width} ${meta.height}" role="img" aria-labelledby="diagram-title diagram-description">
<title id="diagram-title">${escape(meta.title)}</title><desc id="diagram-description">${escape(meta.description)}</desc>
<rect width="100%" height="100%" fill="${escape(source.appState.viewBackgroundColor)}"/>
<g font-family="Arial, 'PingFang SC', 'Noto Sans CJK SC', sans-serif">${chunks.join('\n')}</g>
</svg>\n`;
  const stem = filename.slice(0, -'.excalidraw'.length);
  await writeFile(join(directory, `${stem}.svg`), svg);
  semantic.push({ id: stem, title: meta.title, question: meta.question, status: meta.status,
    evidence: meta.evidence, state: meta.state,
    objects: elements.filter(e => e.customData?.kind).map(e => ({ id: e.id, ...e.customData })) });
  rendered.push({ stem, svg, width: meta.width, height: meta.height });
  console.log(`SVG ${stem} (${meta.width}×${meta.height})`);
}
await writeFile(join(directory, 'architecture-model.json'), JSON.stringify({
  schema_version: 1,
  source: '*.excalidraw element customData; generated, do not edit',
  views: semantic
}, null, 2) + '\n');

if (options.png) {
  const { chromium } = await import(pathToFileURL(options['playwright-module']).href);
  const browser = await chromium.launch({ executablePath: options.browser, headless: true });
  console.log(`Headless Chromium ${browser.version()}`);
  const layoutIssues = [];
  try {
    for (const view of rendered) {
      const page = await browser.newPage({ deviceScaleFactor: 1 });
      await page.route('**/*', route => route.abort());
      await page.setViewportSize({ width: view.width, height: view.height });
      // Only the generated SVG is loaded; external requests are blocked.
      await page.setContent(`<html lang="zh-CN"><meta charset="utf-8"><style>html,body{margin:0;background:#fff}svg{display:block}</style><body>${view.svg}</body></html>`);
      await page.evaluate(() => document.fonts.ready);
      const issues = await page.evaluate(() => [...document.querySelectorAll('svg text')].flatMap(text => {
        const box = text.getBBox();
        const owner = document.getElementById(text.dataset.containerId);
        if (!owner) return [];
        const boundary = owner.getBBox();
        return box.x < boundary.x + 5 || box.y < boundary.y + 5 ||
          box.x + box.width > boundary.x + boundary.width - 5 ||
          box.y + box.height > boundary.y + boundary.height - 5 ? [text.id] : [];
      }));
      if (issues.length) layoutIssues.push(`${view.stem}: ${issues.join(', ')}`);
      await page.locator('svg').screenshot({ path: join(directory, `${view.stem}.png`) });
      await page.close();
      console.log(`PNG ${view.stem}; ${issues.length ? `${issues.length} text bounds issue(s)` : 'container text bounds pass'}`);
    }
  } finally { await browser.close(); }
  if (layoutIssues.length) throw new Error(`Text outside container:\n${layoutIssues.join('\n')}`);
}
