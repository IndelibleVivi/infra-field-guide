/* Local, deterministic search. Shared by the browser and reader-query tests. */
((root) => {
  const normalize = value => value.normalize('NFKC').toLowerCase().replace(/[(),:：，]+/g, ' ').replace(/\s+/g, ' ').trim();
  const compact = value => normalize(value).replace(/\s/g, '');
  const ssh = 'guide/troubleshooting/#ssh-失败时保留能返回的路';
  const resources = 'guide/operations/#5-日志与磁盘先查增长来源再限制';
  // A small editorial vocabulary: symptoms route to existing answers, never new advice.
  const problems = [
    { aliases: ['ssh 超时', '连接超时', 'ssh timeout', 'connection timed out'], groups: [['ssh'], ['timeout', '超时']], target: ssh },
    { aliases: ['ssh 连不上', 'ssh 连接失败'], groups: [['ssh']], target: ssh },
    { aliases: ['公钥拒绝', '公钥被拒绝', 'publickey', 'permission denied', 'permission denied (publickey)'], groups: [['publickey', '公钥'], ['ssh', '登录']], target: ssh },
    { aliases: ['connection refused', '连接被拒绝'], groups: [['refused', '拒绝'], ['ssh', '端口']], target: ssh },
    { aliases: ['host key changed', '主机密钥变了'], groups: [['host key', '主机身份']], target: ssh },
    { aliases: ['磁盘满', '磁盘空间不足', '空间不足', 'no space left', 'no space left on device', '磁盘还有空间但写不了'], groups: [['磁盘', '文件系统'], ['空间', '余量', 'inode']], target: resources },
    { aliases: ['内存爆了', '内存不足', '进程被杀', 'exit 137'], groups: [['oom', '内存'], ['137', '压力', '进程']], target: 'guide/operations/#2-应用慢进程消失先区分是哪一种压力' },
    { aliases: ['网站 502', '网站打不开', 'bad gateway'], groups: [['origin'], ['502', 'http', '网站']], target: 'guide/troubleshooting/#一条-http-请求怎样分段验证' },
    { aliases: ['command not found', '命令找不到', 'ssh 找不到命令'], groups: [['path'], ['非交互']], target: 'guide/private-access/#非交互-ssh-的-path-经常与本地-terminal-不同' },
  ];

  function search(index, input) {
    const query = normalize(input);
    if (!query) return [];
    const packed = compact(query);
    // Prefer the most specific phrase when several aliases overlap.
    const intent = problems.flatMap(problem => problem.aliases.map(alias => ({ problem, alias: compact(alias) })))
      .filter(item => packed.includes(item.alias)).sort((a, b) => b.alias.length - a.alias.length)[0];
    const remainder = intent ? normalize(query.replace(new RegExp([...intent.alias].join('\\s*'), 'u'), ' ')).split(' ').filter(Boolean) : [];
    const groups = intent ? [...intent.problem.groups, ...remainder.map(word => [word])] : query.split(' ').map(word => [word]);
    const terms = [...new Set(groups.flat())].sort((a, b) => b.length - a.length);
    return index.map(section => {
      const heading = normalize(section.heading);
      const title = normalize(section.title);
      const body = normalize(section.text);
      const haystack = title + ' ' + heading + ' ' + body;
      const direct = intent && section.url.endsWith(intent.problem.target) && remainder.every(word => haystack.includes(word));
      if (!direct && !groups.every(group => group.some(word => haystack.includes(word)))) return null;
      const score = (direct ? 80 : 0) + (heading.includes(query) ? 15 : 0) + (body.includes(query) ? 4 : 0) +
        groups.reduce((sum, group) => sum + (group.some(word => heading.includes(word)) ? 8 : group.some(word => title.includes(word)) ? 3 : 1), 0);
      const positions = terms.map(word => section.text.toLowerCase().indexOf(word)).filter(position => position >= 0);
      return { section, score, terms, position: positions.length ? Math.min(...positions) : 0 };
    }).filter(Boolean).sort((a, b) => b.score - a.score);
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { search };
  else root.FieldGuideSearch = { search };
})(globalThis);
