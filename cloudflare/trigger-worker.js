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

export default {
  async scheduled(event, env, ctx) {
    // 打一行日志，便于在 Cloudflare 后台确认它确实触发了
    console.log('[destiny] cron fired at', new Date().toISOString(), event.cron);

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
    if (!resp.ok) {
      throw new Error(`GitHub dispatch failed: ${resp.status} ${text.slice(0, 300)}`);
    }
  },

  // 便于手动验证：浏览器或 curl 打一下这个 Worker 的 URL 即可立刻触发一次，
  // 不用等到第二天早上 8 点再去验证配置是否正确。
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname !== '/trigger') {
      return new Response('destiny-daily scheduler. POST /trigger to fire now.', {
        status: 200,
      });
    }
    await this.scheduled({ cron: 'manual' }, env, ctx);
    return new Response('triggered', { status: 200 });
  },
};
