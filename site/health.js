/* Synthetic playback only. Status and interpretation come from health.py at build time. */
(() => {
  const $ = selector => document.querySelector(selector);
  const configurations = {
    memory: { title: 'RAM 可用余量', short: 'RAM 可用', unit: '%', maximum: 100, threshold: 10, thresholdLabel: '≤10% 需关注', subtitle: '可用比例；越低，给新应用留下的空间越少。' },
    root_bytes: { title: '根文件系统可用空间', short: '磁盘可用', unit: '%', maximum: 100, threshold: 15, thresholdLabel: '≤15% 需关注', subtitle: '普通用户的可用比例；保留块不算作可用余量。' },
    cpu: { title: 'CPU load · 5 分钟', short: 'CPU load', unit: '', maximum: 3, threshold: 2, thresholdLabel: '2 个逻辑 CPU', subtitle: 'Load 是运行与等待的需求，不是 CPU 使用率百分比。' },
    memory_psi: { title: 'Memory PSI · some / 60 秒', short: '内存等待', unit: '%', maximum: 25, threshold: 10, thresholdLabel: 'some ≥10% 需关注', subtitle: '有任务因内存受阻的时间占比；full 的判断也计入状态提示。' },
    root_inodes: { title: '根文件系统 inode 余量', short: 'Inode 可用', unit: '%', maximum: 100, threshold: 15, thresholdLabel: '≤15% 需关注', subtitle: '可用 inode 比例；小文件很多时，字节仍有余量也可能无法创建文件。' },
    swap: { title: 'Swap 使用比例', short: 'Swap 使用', unit: '%', maximum: 100, threshold: 50, thresholdLabel: '≥50% 需关注', subtitle: '已用 swap 不能证明正在频繁换页；结合 RAM、等待和日志判断。' },
  };
  const mainMetrics = ['memory', 'root_bytes', 'cpu', 'memory_psi'];
  const secondary = ['swap', 'root_inodes', 'uptime'];
  let data, scenario, step = 12, selected = 'memory', windowMinutes = 60, timer;
  const escape = text => String(text).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const timestamp = frame => frame.at.slice(11, 16);
  const current = () => scenario.frames[step];
  const stateLabel = metric => metric.status;
  const chartValue = (frame, key) => frame.chart[key];
  const formatValue = (value, config) => value == null ? '未知' : value.toFixed(config.unit ? 1 : 2) + config.unit;

  function pathFor(frames, key, x, y) {
    let path = '', previousKnown = false;
    for (const frame of frames) {
      const value = chartValue(frame, key);
      if (value == null) { previousKnown = false; continue; }
      path += `${previousKnown ? 'L' : 'M'}${x(frame).toFixed(2)},${y(value).toFixed(2)} `;
      previousKnown = true;
    }
    return path;
  }
  function miniTrace(key) {
    const frames = scenario.frames.slice(0, step + 1), config = configurations[key];
    const path = pathFor(frames, key, frame => frame.minute / 60 * 160, value => 22 - value / config.maximum * 20);
    return `<svg class="mini-trace" viewBox="0 0 160 24" preserveAspectRatio="none" aria-hidden="true"><path d="M0 23H160" fill="none" stroke="#d9e8ef"/><path d="${path}" fill="none" stroke="#6ca6c0" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
  }
  function drawChart() {
    const config = configurations[selected], frame = current();
    const width = Math.max(280, Math.round($('#resource-chart').getBoundingClientRect().width));
    const right = width - 16;
    $('#resource-chart').setAttribute('viewBox', `0 0 ${width} 235`);
    const end = frame.minute, start = Math.max(0, end - windowMinutes);
    const frames = scenario.frames.slice(0, step + 1).filter(item => item.minute >= start);
    const x = item => 46 + (item.minute - start) / Math.max(5, end - start) * (right - 46);
    const y = value => 192 - value / config.maximum * 158;
    const nodes = [`<title id="chart-accessible-title">${escape(config.title)}的合成趋势</title><desc id="chart-accessible-desc">从模拟第 ${start} 到 ${end} 分钟，当前 ${escape(formatValue(chartValue(frame, selected), config))}。缺失读数保留空缺，不记为零。</desc>`];
    for (let tick = 0; tick <= 4; tick++) {
      const value = config.maximum * tick / 4, py = y(value);
      nodes.push(`<path d="M46 ${py}H${right}" stroke="#e7eef3" fill="none"/><text x="35" y="${py + 4}" text-anchor="end" fill="#6a8191" font-size="11">${Number(value.toFixed(2))}${config.unit}</text>`);
    }
    const thresholdY = y(config.threshold);
    nodes.push(`<path d="M46 ${thresholdY}H${right}" stroke="#d5bd83" stroke-dasharray="4 5"/><text x="${right - 2}" y="${thresholdY - 7}" text-anchor="end" fill="#917438" font-size="10">${escape(config.thresholdLabel)}</text>`);
    const path = pathFor(frames, selected, x, y);
    nodes.push(`<path d="${path}" fill="none" stroke="#2e83aa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`);
    for (const item of frames) {
      const value = chartValue(item, selected);
      if (value != null) nodes.push(`<circle cx="${x(item)}" cy="${y(value)}" r="${item === frame ? 4 : 2.3}" fill="#2e83aa"><title>${timestamp(item)} · ${formatValue(value, config)}</title></circle>`);
      else nodes.push(`<path d="M${x(item)-3} 189l6 6m-6 0 6-6" stroke="#8799a6"/><text x="${x(item)}" y="178" text-anchor="middle" fill="#7b8b96" font-size="10">缺失</text>`);
    }
    const times = frames.length < 3 ? frames : [frames[0], frames[Math.floor((frames.length - 1) / 2)], frames[frames.length - 1]];
    for (const item of times) nodes.push(`<text x="${x(item)}" y="217" text-anchor="middle" fill="#6a8191" font-size="11">${timestamp(item)}</text>`);
    $('#resource-chart').innerHTML = nodes.join('');
    $('#chart-title').textContent = config.title;
    $('#chart-description').textContent = config.subtitle;
    $('#chart-current').textContent = `当前 ${formatValue(chartValue(frame, selected), config)}`;
    $('#explanation-label').textContent = config.title;
    $('#metric-explanation').textContent = frame.metrics[selected].note;
  }
  function render() {
    const frame = current();
    $('#scenario-title').textContent = scenario.title;
    $('#frame-time').textContent = `模拟时间 ${timestamp(frame)} UTC`;
    $('#elapsed').textContent = `${frame.minute} min`;
    $('#moment').value = step;
    $('#moment').style.setProperty('--position', `${step / 12 * 100}%`);
    $('#moment').setAttribute('aria-valuetext', `模拟第 ${frame.minute} 分钟，${timestamp(frame)} UTC`);
    for (const key of mainMetrics) {
      const metric = frame.metrics[key], tile = $(`[data-metric="${key}"]`);
      tile.className = 'metric-tile ' + metric.state;
      tile.setAttribute('aria-pressed', String(key === selected));
      tile.setAttribute('aria-label', `${configurations[key].short}，${metric.main}，${stateLabel(metric)}；查看趋势`);
      tile.innerHTML = `<span class="metric-top"><span class="metric-label">${configurations[key].short}</span><span class="status-dot">${escape(stateLabel(metric))}</span></span><strong class="metric-value">${escape(metric.main)}</strong><span class="metric-sub">${escape(key === 'cpu' ? '5 分钟 load / 2 个逻辑 CPU' : key === 'memory_psi' ? 'some / 最近 60 秒' : '普通使用的可用余量')}</span>${miniTrace(key)}`;
    }
    for (const key of secondary) {
      const metric = frame.metrics[key], tile = $(`[data-secondary="${key}"]`);
      tile.className = 'secondary-metric ' + metric.state;
      if (key !== 'uptime') {
        tile.setAttribute('aria-pressed', String(key === selected));
        tile.setAttribute('aria-label', `${metric.label}，${metric.main}，${metric.status}；查看趋势`);
      }
      tile.innerHTML = `<div class="metric-top"><span class="metric-label">${escape(metric.label)}</span><span class="status-dot">${escape(stateLabel(metric))}</span></div><strong class="metric-value">${escape(metric.main)}</strong><p class="secondary-detail">${escape(metric.detail)}</p>`;
    }
    const attention = Object.values(frame.metrics).filter(metric => ['critical','warning','unknown'].includes(metric.state)).sort((a,b) => ['critical','warning','unknown'].indexOf(a.state) - ['critical','warning','unknown'].indexOf(b.state));
    const warnings = attention.filter(metric => metric.state !== 'unknown').length;
    const unknown = attention.length - warnings;
    const summary = `${warnings} 项需关注 · ${unknown} 项未知`;
    if ($('#status-summary').textContent !== summary) $('#status-summary').textContent = summary;
    $('#attention-list').innerHTML = attention.length ? attention.map(metric => `<li class="${metric.state}"><span>${escape(metric.label)}</span><span>${escape(metric.status)}</span></li>`).join('') : '<li><span>已取得的指标未触及提示阈值</span><span>继续观察</span></li>';
    $('#scenario-lesson').textContent = scenario.lesson;
    drawChart();
  }
  function stop() {
    clearInterval(timer); timer = undefined;
    $('#play').classList.remove('is-playing');
    $('#play span').textContent = '回放变化';
    $('#play').setAttribute('aria-label', '回放合成场景变化');
  }
  function selectScenario(id) {
    stop(); scenario = data.scenarios.find(item => item.id === id); step = 12;
    selected = ({disk:'root_bytes', inodes:'root_inodes'})[id] || 'memory';
    document.querySelectorAll('[data-scenario]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scenario === id)));
    render();
  }
  function selectMetric(key) {
    selected = key;
    document.querySelectorAll('[data-metric]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.metric === key)));
    drawChart();
  }
  $('#play').addEventListener('click', () => {
    if (timer) { stop(); return; }
    if (step === 12) step = 0;
    render(); $('#play').classList.add('is-playing'); $('#play span').textContent = '暂停回放'; $('#play').setAttribute('aria-label', '暂停合成场景回放');
    timer = setInterval(() => { step++; render(); if (step === 12) stop(); }, 1400);
  });
  $('#restart').addEventListener('click', () => { stop(); step = 0; render(); });
  $('#moment').addEventListener('input', event => { stop(); step = Number(event.target.value); render(); });
  document.querySelectorAll('[data-window]').forEach(button => button.addEventListener('click', () => {
    windowMinutes = Number(button.dataset.window);
    document.querySelectorAll('[data-window]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    drawChart();
  }));
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  fetch('scenarios.json').then(response => { if (!response.ok) throw new Error('Cannot load synthetic scenarios'); return response.json(); }).then(result => {
    data = result;
    $('#scenarios').innerHTML = data.scenarios.map((item, index) => `<button type="button" class="scenario-choice" data-scenario="${item.id}" aria-pressed="false" title="${escape(item.description)}"><span class="scene-number" aria-hidden="true">0${index+1}</span><span>${escape(item.title)}</span></button>`).join('');
    document.querySelectorAll('[data-scenario]').forEach(button => button.addEventListener('click', () => selectScenario(button.dataset.scenario)));
    for (const key of mainMetrics) {
      const button = document.createElement('button'); button.type = 'button'; button.dataset.metric = key;
      button.addEventListener('click', () => selectMetric(key));
      $('#primary-metrics').append(button);
    }
    for (const key of secondary) {
      const tile = document.createElement(key === 'uptime' ? 'article' : 'button');
      tile.dataset.secondary = key;
      if (key !== 'uptime') {
        tile.type = 'button'; tile.dataset.metric = key;
        tile.addEventListener('click', () => selectMetric(key));
      }
      $('#secondary-metrics').append(tile);
    }
    $('#load-status').hidden = true; $('#dashboard').hidden = false; selectScenario('everyday');
    new ResizeObserver(() => drawChart()).observe($('.chart-panel'));
  }).catch(() => { $('#load-status').textContent = '合成数据暂时没有加载成功。请刷新页面，或从工具说明进入离线快照。'; });
})();
