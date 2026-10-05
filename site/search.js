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
    { aliases: ['时间不准', '时间校准', 'synchronized no', 'ntpsynchronized'], groups: [['时间'], ['校时', '同步']], target: 'reference/time-synchronization/#只读检查时间服务' },
    { aliases: ['udp123', 'udp 123', 'ntp 不通', 'ntp 无响应', '123 被封'], groups: [['udp'], ['123']], target: 'reference/time-synchronization/#区分-udp-123-的请求与回包' },
    { aliases: ['kvm-clock', 'kvm clock'], groups: [['kvm-clock']], target: 'reference/time-synchronization/#时钟源与校时服务' },
    { aliases: ['utc 本地时间', '时区换算', '差八小时'], groups: [['utc'], ['时区', '本地']], target: 'reference/time-synchronization/#utc时区与本地显示' },
    { aliases: ['时间 hook', 'hook 时间', '会话时间'], groups: [['hook'], ['时间']], target: 'reference/time-synchronization/#给-agent-注入时间' },
    { aliases: ['每天九点', '夏令时', '单调时钟'], groups: [['定时', '时钟'], ['时长', '日历']], target: 'reference/time-synchronization/#定时触发与经过时长' },
    { aliases: ['多 harness', '跨机器 agent', '跨 harness', '不同 cli', 'agent 在哪执行'], groups: [['harness', 'agent'], ['机器', '执行']], target: 'reference/multi-machine-operations/#先定位实际执行位置' },
    { aliases: ['任务超时重跑', '原任务恢复', '远程任务断线'], groups: [['任务'], ['超时', '恢复']], target: 'reference/multi-machine-operations/#断线超时与原任务恢复' },
    { aliases: ['ssh 锁死', '加固后连不上', '只有机能登录'], groups: [['ssh'], ['旧', '新连接']], target: 'reference/access-control-recovery/#已经有人进不去了' },
    { aliases: ['fail2ban'], groups: [['fail2ban']], target: 'reference/access-control-recovery/#fail2ban-与定点恢复' },
    { aliases: ['撤销 key', '删除公钥', '撤掉 key'], groups: [['key', '公钥'], ['撤', '删除']], target: 'reference/access-control-recovery/#撤销-key-后还有什么没有结束' },
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
