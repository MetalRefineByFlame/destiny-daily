// Cloudflare Worker —— 可靠的外部调度器
//
// 背景：GitHub Actions 自家的 schedule 触发器自 2026-08 起出现平台级故障
//       （延迟数小时甚至完全不触发，而 workflow_dispatch 正常）。
//       社区公认的解法是：用一个可靠的外部定时源去调 GitHub 的 dispatch API。
//
// 本 Worker 做的事很简单：收到 Cron 触发 -> 调 GitHub repository_dispatch API。
// 真正的报告生成仍在 GitHub Actions 上跑原生 Python，无需改动术数引擎。
//
// Cloudflare Free 套餐：每账户 5 个 Cron Trigger，本任务只用 1 个，足够。
// CPU 10ms 限制对本 Worker 毫无压力（只发一个 HTTP 请求）。

// 统一入口：不管 cron 还是手动 /trigger，都走这里。
// 设计原则：**不抛异常**。任何失败都返回 502 + 明确 JSON，
// 因为在 Worker 里 uncaught exception 只会变成 Cloudflare 的 1101 错误页，
// 看不到任何线索，排查成本极高。
async function fire(env) {
  const missing = ['GITHUB_OWNER', 'GITHUB_REPO', 'GITHUB_TOKEN']
    .filter((k) => !env[k]);
  if (missing.length) {
    const msg = `Missing bindings: ${missing.join(', ')}. 请在 wrangler.toml [vars] 配置，GITHUB_TOKEN 用 wrangler secret put 写入。`;
    console.error('[destiny]', msg);
    return { ok: false, status: 500, text: msg };
  }

  const resp = await fetch(
    `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`,
    {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github+json',
        'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
        'User-Agent': 'destiny-daily-scheduler',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      body: JSON.stringify({ event_type: 'daily-destiny' }),
    }
  );

  // repository_dispatch 成功时返回 204 No Content
  const text = await resp.text();
  console.log('[destiny] github responded', resp.status, text.slice(0, 200));
  return { ok: resp.ok, status: resp.status, text: text.slice(0, 300) };
}

export default {
  async scheduled(event, env) {
    console.log('[destiny] cron fired at', new Date().toISOString(), event.cron);
    const r = await fire(env);
    if (!r.ok) {
      // 这里仍 throw，是为了让 Cloudflare 后台把这次 cron 标记为失败，便于告警。
      // 但 fetch 路径永远不会走到这里，手动验证总能看到可读的错误信息。
      throw new Error(`GitHub dispatch failed: ${r.status} ${r.text}`);
    }
  },

  // 便于手动验证：浏览器或 curl 打一下 /trigger 即可立刻触发一次，
  // 不用等到第二天早上 8 点再去验证配置是否正确。
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/health') {
      const bound = (k) => Boolean(env[k]);
      return new Response(
        JSON.stringify({
          ok: true,
          time: new Date().toISOString(),
          bindings: {
            GITHUB_OWNER: bound('GITHUB_OWNER'),
            GITHUB_REPO: bound('GITHUB_REPO'),
            GITHUB_TOKEN: bound('GITHUB_TOKEN'),
          },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json; charset=utf-8' } }
      );
    }
    if (url.pathname !== '/trigger') {
      return new Response(
        'destiny-daily scheduler. GET /health 查看配置状态，POST/GET /trigger 立即触发一次。',
        { status: 200 }
      );
    }

    const r = await fire(env);
    return new Response(
      JSON.stringify({ ok: r.ok, github_status: r.status, detail: r.text }),
      {
        status: r.ok ? 200 : 502,
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
      }
    );
  },
};
