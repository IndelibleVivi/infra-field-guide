/* Run after python site/build.py; exercise the same function shipped to browsers. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { search } = require('./search.js');
const index = JSON.parse(readFileSync(new URL('../_site/search.json', `file://${__filename}`), 'utf8'));
const ssh = 'guide/troubleshooting/#ssh-失败时保留能返回的路';
const disk = 'guide/operations/#5-日志与磁盘先查增长来源再限制';
const queries = [
  ['SSH 超时', ssh], ['SSH timeout', ssh], ['连接超时', ssh], ['SSH 连不上', ssh],
  ['磁盘满', disk], ['空间不足', disk], ['No space left on device', disk],
  ['公钥拒绝', ssh], ['SSH publickey', ssh], ['Permission denied (publickey)', ssh],
  ['connection refused', ssh], ['host key changed', ssh],
  ['内存不足', 'guide/operations/#2-应用慢进程消失先区分是哪一种压力'],
  ['exit 137', 'guide/operations/#2-应用慢进程消失先区分是哪一种压力'],
  ['网站 502', 'guide/troubleshooting/#一条-http-请求怎样分段验证'],
  ['command not found', 'guide/private-access/#非交互-ssh-的-path-经常与本地-terminal-不同'],
  ['swap', 'guide/operations/#3-swap-是缓冲不是-oom-的治疗方案'],
  ['备份 恢复', 'guide/operations/#7-备份至少要成功恢复一次'],
  ['DNS TTL', 'guide/vps-to-vps/#路径-a直接-dns-指向新-origin'],
  ['时间不准', 'reference/time-synchronization/#只读检查时间服务'],
  ['UDP123', 'reference/time-synchronization/#区分-udp-123-的请求与回包'],
  ['NTP 不通', 'reference/time-synchronization/#区分-udp-123-的请求与回包'],
  ['kvm-clock', 'reference/time-synchronization/#时钟源与校时服务'],
  ['UTC 本地时间', 'reference/time-synchronization/#utc时区与本地显示'],
  ['时间 hook', 'reference/time-synchronization/#给-agent-注入时间'],
  ['夏令时', 'reference/time-synchronization/#定时触发与经过时长'],
  ['多 harness', 'reference/multi-machine-operations/#先定位实际执行位置'],
  ['任务超时重跑', 'reference/multi-machine-operations/#断线超时与原任务恢复'],
  ['加固后连不上', 'reference/access-control-recovery/#已经有人进不去了'],
  ['fail2ban', 'reference/access-control-recovery/#fail2ban-与定点恢复'],
  ['撤销 key', 'reference/access-control-recovery/#撤销-key-后还有什么没有结束'],
  ['配置没生效', 'reference/configuration-and-runtime/#配置来自哪一层'],
  ['终端能跑服务不行', 'reference/configuration-and-runtime/#shell-环境与-service-环境的差异'],
  ['服务版本不一致', 'reference/configuration-and-runtime/#各层不是同一个版本'],
  ['daemon-reload', 'reference/configuration-and-runtime/#daemon-reloadreload-与-restart'],
  ['定时任务漏跑', 'reference/scheduled-jobs/#persistent-只作用-oncalendar'],
  ['Persistent', 'reference/scheduled-jobs/#persistent-只作用-oncalendar'],
  ['上次没跑完', 'reference/scheduled-jobs/#同-service-仍-active-时-timer-不重启它'],
  ['cron 时区', 'reference/scheduled-jobs/#cron-还是-systemd-timer'],
  ['删了磁盘没变', 'reference/data-lifecycle/#已删除但仍被打开的文件'],
  ['SQLite DELETE', 'reference/data-lifecycle/#sqlitedeletevacuum-与-wal'],
  ['VACUUM 空间', 'reference/data-lifecycle/#vacuum-的代价与替代'],
  ['WAL 很大', 'reference/data-lifecycle/#wal-模式的边界'],
  ['备份保留', 'reference/data-lifecycle/#日志journal-与备份的保留'],
];
for (const [query, destination] of queries) test(`读者问法：${query}`, () => {
  const matches = search(index, query);
  assert.ok(matches.length > 0);
  assert.ok(matches[0].section.url.endsWith(destination), matches[0].section.url);
});
test('multiple keywords narrow results, including an alias with additional words', () => {
  const matches = search(index, 'SSH 公钥拒绝 用户');
  assert.ok(matches[0].section.url.endsWith(ssh));
  assert.ok(matches.every(({section}) => (section.title + section.heading + section.text).includes('用户')));
  assert.equal(search(index, 'SSH 公钥拒绝 nonexistentkeyword').length, 0);
});
test('empty, missing, whitespace and case/full-width queries', () => {
  assert.deepEqual(search(index, ''), []);
  assert.deepEqual(search(index, '没有这种故障qwerty'), []);
  assert.equal(search(index, ' ＳＳＨ   TIMEOUT ')[0].section.url, search(index, 'SSH 超时')[0].section.url);
});
