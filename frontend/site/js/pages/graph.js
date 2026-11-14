import { api } from '../api.js';
import { ENUMS, badgeTone, can } from '../config.js';
import { chips, cyclePath, drawer, emptyState, errorBox, errorMessage, esc, filterBar, impactRows, kv, table, toast } from '../ui.js';

const state = { kind: '' };

function openCycle(view, ctx, cycle) {
  drawer({
    title: `依赖环 · ${cycle.length} 个指标`,
    subtitle: `${cycle.id} · 影响分 ${cycle.score}`,
    body: `
      ${cyclePath(cycle.path)}
      <dl class="kv">
        <dt>环上指标</dt><dd>${esc(cycle.metric_names.join(' / '))}</dd>
        <dt>成员编码</dt><dd class="mono">${esc(cycle.members.join(' , '))}</dd>
        <dt>严重度</dt><dd><span class="badge ${badgeTone(cycle.severity)}">${esc(ENUMS.severity[cycle.severity])}</span></dd>
        <dt>影响分</dt><dd class="mono">${esc(cycle.score)}（核心报表 ×3）</dd>
      </dl>
      <div class="dsl-box">
        <span class="label">下游报表影响面</span>
        ${impactRows(cycle.impact)}
      </div>
      <div class="dsl-box">
        <span class="label">建议动作</span>
        <p class="section-note">${esc(cycle.suggestion)}</p>
      </div>`,
  });
}

function openNode(view, ctx, node, edges) {
  const outgoing = edges.filter((edge) => edge.from === node.code && edge.kind === 'metric');
  drawer({
    title: `${node.name} · ${node.code}`,
    subtitle: `${node.domain_label} / 版本 v${node.version} / 下游报表 ${node.report_count} 张`,
    body: `
      ${kv([
        ['解析状态', `<span class="badge ${node.parse_status === 'ok' ? 'ok' : 'danger'}">${esc(ENUMS.parseStatus[node.parse_status] || node.parse_status)}</span>`],
        ['分级', esc(ENUMS.metricTier[node.tier] || node.tier)],
        ['是否在环上', node.in_cycle ? '<span class="badge danger">在环上</span>' : '否'],
        ['依赖指标数', esc(node.dep_count)],
        ['下游报表数', esc(node.report_count)],
      ])}
      <div class="dsl-box">
        <span class="label">该指标引用的指标（出边）</span>
        ${outgoing.length ? chips(outgoing.map((edge) => edge.to)) : '<p class="muted">没有引用其他指标。</p>'}
      </div>
      <div class="dsl-box">
        <span class="label">消费该指标的报表</span>
        ${chips(node.reports || [])}
      </div>`,
  });
}

export const graphPage = {
  async render(view, ctx) {
    let graph;
    let deps;
    try {
      graph = await api.get('/api/graph');
      deps = await api.get('/api/dependencies', { kind: state.kind, limit: 200 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => graphPage.render(view, ctx));
      return;
    }
    const stats = graph.stats;
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head"><h2>依赖图概览</h2><span class="meta">algorithm B · tarjan</span></div>
        <div class="panel-body">
          <div class="stat-strip">
            <div class="stat"><span class="k">NODES</span><span class="v">${esc(stats.nodes)}</span><span class="hint">指标节点</span></div>
            <div class="stat"><span class="k">DEP EDGES</span><span class="v">${esc(stats.dep_edges)}</span><span class="hint">指标 → 指标</span></div>
            <div class="stat"><span class="k">REPORT EDGES</span><span class="v">${esc(stats.report_edges)}</span><span class="hint">报表引用</span></div>
            <div class="stat"><span class="k">CYCLES</span><span class="v">${esc(stats.cycles)}</span><span class="hint">环上节点 ${esc(stats.cycle_nodes)} 个</span></div>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>依赖环（SCC）</h2><span class="meta">cycles</span></div>
        <div class="panel-body">
          ${
            graph.cycles.length
              ? `<div class="list-tight">${graph.cycles
                  .map(
                    (cycle, index) => `<div class="impact-row" data-cycle="${index}" style="cursor:pointer;align-items:flex-start">
                      <div style="display:grid;gap:6px">
                        <span class="index-tag">RING ${String(index + 1).padStart(2, '0')} · 长度 ${esc(cycle.length)}</span>
                        ${cyclePath(cycle.path)}
                      </div>
                      <div style="display:flex;gap:8px;align-items:center">
                        <span class="badge ${badgeTone(cycle.severity)}">${esc(ENUMS.severity[cycle.severity])}</span>
                        <span class="mono tiny">${esc(cycle.score)} 分</span>
                        <button class="btn sm ghost" data-open-cycle="${index}">展开</button>
                      </div>
                    </div>`,
                  )
                  .join('')}</div>`
              : emptyState({ title: '没有依赖环', hint: '依赖图当前是有向无环图（DAG）。' })
          }
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>指标节点</h2><span class="meta">${graph.nodes.length} 个</span></div>
        ${table({
          rows: graph.nodes,
          columns: [
            { key: 'code', label: '索引号', className: 'mono', render: (row) => `<span class="index-tag">${esc(row.code)}</span>` },
            { key: 'name', label: '指标名称', render: (row) => `<b>${esc(row.name)}</b>` },
            { key: 'domain_label', label: '业务域' },
            { key: 'dep_count', label: '出边', className: 'num' },
            { key: 'report_count', label: '报表', className: 'num' },
            {
              key: 'in_cycle',
              label: '状态',
              render: (row) => (row.in_cycle ? '<span class="badge danger">在环上</span>' : '<span class="badge ok">正常</span>'),
            },
            {
              key: 'parse_status',
              label: '解析',
              render: (row) => `<span class="badge ${row.parse_status === 'ok' ? 'ok' : 'danger'}">${esc(ENUMS.parseStatus[row.parse_status] || row.parse_status)}</span>`,
            },
          ],
          empty: { title: '没有节点', hint: '先 seed 或注册指标。' },
        })}
      </section>
      <section class="panel">
        <div class="panel-head"><h2>依赖边清单</h2><span class="meta">${deps.total} 条</span></div>
        ${filterBar('dep-filters', [
          { label: '边类型', name: 'kind', value: state.kind, options: [{ value: '', label: '全部类型' }, ...Object.entries(ENUMS.dependencyKind).map(([value, label]) => ({ value, label }))] },
        ])}
        ${table({
          rows: deps.items,
          columns: [
            { key: 'from_metric_code', label: '起点指标', className: 'mono' },
            { key: 'kind', label: '边类型', render: (row) => `<span class="badge info">${esc(ENUMS.dependencyKind[row.kind] || row.kind)}</span>` },
            { key: 'to_ref', label: '终点 / 字段 / 报表', className: 'mono' },
            { key: 'weight', label: '权重', className: 'num' },
            { key: 'note', label: '说明' },
          ],
          empty: { title: '还没有依赖边', hint: '跑一次校验运行会按当前口径重建依赖边。' },
        })}
      </section>`;

    view.querySelector('#dep-filters')?.addEventListener('change', (event) => {
      state.kind = event.target.value;
      graphPage.render(view, ctx);
    });
    view.querySelectorAll('[data-open-cycle]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        openCycle(view, ctx, graph.cycles[Number(button.dataset.openCycle)]);
      });
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const code = row.querySelector('.index-tag')?.textContent;
        const node = graph.nodes.find((item) => item.code === code);
        if (node) openNode(view, ctx, node, graph.edges);
      });
    });
  },
};

export default graphPage;
