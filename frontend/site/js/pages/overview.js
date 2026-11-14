import { api } from '../api.js';
import { BRAND, ENUMS, badgeTone, can } from '../config.js';
import { barList, cyclePath, emptyState, errorBox, errorMessage, esc, fmtTime, statStrip, table, trendChart } from '../ui.js';

export const overviewPage = {
  async render(view, ctx) {
    view.innerHTML = '<div class="empty"><div class="mark">正在抽取卡片…</div></div>';
    let data;
    try {
      data = await api.get('/api/overview');
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => overviewPage.render(view, ctx));
      return;
    }
    const latest = data.latest_run;
    view.innerHTML = `
      <div class="section-note">目录索引 · ${esc(BRAND.org)} · 口径 ${data.metrics_total} 条 / 报表 ${data.reports_total} 张（核心 ${data.core_reports} 张）· 后台任务 ${
        data.worker_alive ? '在岗' : '心跳超时'
      }</div>
      ${statStrip([
        { label: 'M · 指标登记', value: data.metrics_total, hint: '48 条口径卡片' },
        { label: 'R · 报表引用', value: data.reports_total, hint: `核心报表 ${data.core_reports} 张（权重 ×3）` },
        { label: 'C · 同名冲突', value: data.conflicts_total, hint: '同名但字段/过滤/聚合不同' },
        { label: 'L · 依赖环', value: data.cycles_total, hint: data.cycle_paths[0] ? 'SCC 检出' : '暂无环' },
        { label: 'H · 高风险', value: data.high_risk, hint: '影响面 ≥ 核心报表级' },
        { label: 'A · 待审批', value: data.pending_changes, hint: '变更单等管理员批准' },
      ])}
      <div class="grid-2">
        <section class="panel">
          <div class="panel-head"><h2>冲突按等级</h2><span class="meta">severity</span></div>
          <div class="panel-body">${
            data.severity.some((item) => item.count > 0)
              ? barList(data.severity.map((item) => ({ ...item, count: item.count })))
              : emptyState({ title: '没有检出冲突', hint: '改一条口径后跑一次校验运行。' })
          }</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>差异类型 / 业务域</h2><span class="meta">kind · domain</span></div>
          <div class="panel-body">
            ${data.conflict_kinds.length ? barList(data.conflict_kinds, 'warn') : '<p class="muted">暂无同名冲突。</p>'}
            <hr class="hr" />
            ${data.domains.length ? barList(data.domains, 'ok') : '<p class="muted">还没有指标。</p>'}
          </div>
        </section>
      </div>
      <section class="panel">
        <div class="panel-head">
          <h2>同名不同口径 · 前 5 条</h2>
          <div style="display:flex;gap:10px;align-items:center">
            <span class="meta">conflicts</span>
            <button class="btn sm ghost" id="goto-conflicts">查看全部</button>
          </div>
        </div>
        ${table({
          rows: data.top_conflicts,
          columns: [
            { key: 'name', label: '同名指标', render: (row) => `<b>${esc(row.name)}</b>` },
            { key: 'kind_label', label: '差异类型', render: (row) => esc(row.kind_label) },
            {
              key: 'severity',
              label: '严重度',
              render: (row) => `<span class="badge ${badgeTone(row.severity)}">${esc(ENUMS.severity[row.severity] || row.severity)}</span>`,
            },
            { key: 'metric_codes', label: '口径成员', className: 'mono', render: (row) => esc(row.metric_codes.join(' / ')) },
            { key: 'report_count', label: '下游报表', className: 'num', render: (row) => esc(row.report_count) },
            { key: 'score', label: '影响分', className: 'num', render: (row) => esc(row.score) },
          ],
          empty: { title: '没有同名冲突', hint: '48 条口径目前没有同名不同口径的情况。' },
        })}
      </section>
      <div class="grid-2">
        <section class="panel">
          <div class="panel-head"><h2>依赖环路径</h2><span class="meta">tarjan scc</span></div>
          <div class="panel-body">
            ${
              data.cycle_paths.length
                ? `<div class="list-tight">${data.cycle_paths
                    .map(
                      (path) =>
                        `<div>${cyclePath(path.split(' → '))}<div class="muted tiny" style="margin-top:6px">环上指标改一处即可打断引用链。</div></div>`,
                    )
                    .join('')}</div>`
                : emptyState({ title: '没有依赖环', hint: '当前依赖图是有向无环的。' })
            }
          </div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>最近校验运行</h2><span class="meta">latest run</span></div>
          <div class="panel-body">
            ${
              latest
                ? `<dl class="kv">
                    <dt>运行号</dt><dd class="mono">${esc(latest.run_no)}</dd>
                    <dt>状态</dt><dd>${esc(latest.status_label)}</dd>
                    <dt>开始</dt><dd>${fmtTime(latest.started_at)}</dd>
                    <dt>输入</dt><dd>${esc(latest.input_count)} 条口径</dd>
                    <dt>问题</dt><dd>${esc(latest.output_count)} 条（冲突 + 环 + 解析失败）</dd>
                  </dl>
                  <hr class="hr" />
                  <div class="section-note">${esc(BRAND.subtitle)}</div>`
                : emptyState({ title: '还没有校验运行', hint: '去「变更单与导出」跑一次。' })
            }
          </div>
        </section>
      </div>
      <section class="panel">
        <div class="panel-head"><h2>近 7 天校验运行</h2><span class="meta">runs / day</span></div>
        <div class="panel-body">${trendChart(data.trend)}</div>
      </section>`;

    view.querySelector('#goto-conflicts')?.addEventListener('click', () => {
      location.hash = '#/conflicts';
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        location.hash = '#/conflicts';
      });
    });
    if (!can(ctx.user.role, 'conflict:read')) {
      view.querySelector('#goto-conflicts')?.remove();
    }
  },
};

export default overviewPage;
