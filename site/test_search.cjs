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
