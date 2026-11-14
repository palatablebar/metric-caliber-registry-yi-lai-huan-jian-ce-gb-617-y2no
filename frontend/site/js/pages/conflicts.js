import { api } from '../api.js';
import { ENUMS, badgeTone, can } from '../config.js';
import { chips, drawer, emptyState, errorBox, errorMessage, esc, field, filterBar, impactRows, kv, table, toast } from '../ui.js';

const state = { severity: '', kind: '' };

function variantCard(metric, index) {
  return `<div class="diff-col">
    <h4>口径 ${String(index + 1).padStart(2, '0')} · ${esc(metric.code)}</h4>
    <p class="section-note">${esc(metric.expression || '—')}</p>
    <div class="dsl-box"><span class="label">字段</span>${chips(metric.fields, { withIndex: false })}</div>
    <div class="dsl-box"><span class="label">过滤</span>${chips(metric.filters, { withIndex: false })}</div>
    <div class="dsl-box"><span class="label">聚合</span>${chips(metric.aggs, { withIndex: false })}</div>
  </div>`;
}

function openConflict(view, ctx, conflict) {
  const writable = can(ctx.user.role, 'change:write');
  const first = conflict.metrics[0];
  const { root, close } = drawer({
    title: `同名冲突 · ${conflict.name}`,
    subtitle: `${conflict.metric_codes.join(' vs ')} · ${ENUMS.conflictKind[conflict.kind] || conflict.kind}`,
    body: `
      ${kv([
        ['差异类型', esc(ENUMS.conflictKind[conflict.kind] || conflict.kind)],
        ['严重度', `<span class="badge ${badgeTone(conflict.severity)}">${esc(ENUMS.severity[conflict.severity])}</span>`],
        ['影响分', `<span class="mono">${esc(conflict.score)}</span>`],
        ['下游报表', `${esc(conflict.impact.report_count)} 张（核心 ${esc(conflict.impact.core_count)} 张）`],
      ])}
      <div class="diff-cols">${conflict.metrics.map(variantCard).join('')}</div>
      <div class="dsl-box">
        <span class="label">差异明细</span>
        <div class="list-tight">
          <div class="impact-row"><span>仅 ${esc(conflict.metrics[0].code)} 有的字段</span><span class="mono">${esc((conflict.diff.fields_only_first || []).join(' / ') || '—')}</span></div>
          <div class="impact-row"><span>仅其他口径有的字段</span><span class="mono">${esc((conflict.diff.fields_only_others || []).join(' / ') || '—')}</span></div>
          <div class="impact-row"><span>仅 ${esc(conflict.metrics[0].code)} 的过滤条件</span><span class="mono">${esc((conflict.diff.filters_only_first || []).join(' ; ') || '—')}</span></div>
          <div class="impact-row"><span>仅其他口径的过滤条件</span><span class="mono">${esc((conflict.diff.filters_only_others || []).join(' ; ') || '—')}</span></div>
        </div>
      </div>
      <div class="dsl-box">
        <span class="label">影响面 · 下游报表（核心报表权重 ×3）</span>
        ${impactRows(conflict.impact)}
      </div>
      <div class="dsl-box">
        <span class="label">建议动作</span>
        <p class="section-note">${esc(conflict.suggestion)}</p>
      </div>
      ${
        writable
          ? `<div class="dsl-box">
              <span class="label">把这份冲突变成变更单</span>
              ${field({ label: '变更指标', name: 'metric_code', value: first.code, options: conflict.metrics.map((item) => ({ value: item.code, label: `${item.code} · ${item.name}` })) })}
              ${field({ label: '原因（月会结论 / 数仓变更）', name: 'reason', value: `同名冲突「${conflict.name}」：${conflict.suggestion}` })}
              <button class="btn sm accent" id="create-cr" type="button">提交变更单</button>
            </div>`
          : '<p class="muted tiny">只读角色可以查看冲突与影响面，提交变更单需要专员及以上角色。</p>'
      }`,
  });

  root.querySelector('#create-cr')?.addEventListener('click', async () => {
    const metricCode = root.querySelector('[name=metric_code]')?.value || first.code;
    const reason = root.querySelector('[name=reason]')?.value || '';
    try {
      await api.post('/api/change-requests', {
        change_kind: 'caliber',
        target_ref: metricCode,
        metric_code: metricCode,
        reason,
      });
      toast('变更单已提交，等待管理员审批');
      close();
      await conflictsPage.render(view, ctx);
    } catch (err) {
      toast(err.code === 'CONFLICT' ? '该指标已有待审批的同类变更单' : errorMessage(err), 'err');
    }
  });
}

export const conflictsPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/conflicts', { severity: state.severity, kind: state.kind, limit: 50 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => conflictsPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>同名不同口径 · 冲突与影响面</h2>
          <div style="display:flex;gap:10px;align-items:center">
            <span class="meta">${data.total} 处</span>
            ${can(ctx.user.role, 'export:read') ? '<button class="btn sm ghost" id="export-conflicts">导出 CSV</button>' : ''}
          </div>
        </div>
        ${filterBar('conflict-filters', [
          { label: '严重度', name: 'severity', value: state.severity, options: [{ value: '', label: '全部等级' }, ...Object.entries(ENUMS.severity).map(([value, label]) => ({ value, label }))] },
          { label: '差异类型', name: 'kind', value: state.kind, options: [{ value: '', label: '全部类型' }, ...Object.entries(ENUMS.conflictKind).map(([value, label]) => ({ value, label }))] },
        ])}
        ${table({
          rows: data.items,
          columns: [
            { key: 'name', label: '同名指标', render: (row) => `<b>${esc(row.name)}</b>` },
            {
              key: 'kind',
              label: '差异类型',
              render: (row) => `<span class="badge warn">${esc(ENUMS.conflictKind[row.kind] || row.kind)}</span>`,
            },
            {
              key: 'severity',
              label: '严重度',
              render: (row) => `<span class="badge ${badgeTone(row.severity)}">${esc(ENUMS.severity[row.severity])}</span>`,
            },
            { key: 'metric_codes', label: '口径成员', className: 'mono', render: (row) => esc(row.metric_codes.join(' / ')) },
            { key: 'score', label: '影响分', className: 'num' },
            { key: 'impact', label: '下游报表', className: 'num', render: (row) => esc(row.impact.report_count) },
            { key: 'suggestion', label: '建议动作', render: (row) => `<span class="tiny">${esc(row.suggestion.slice(0, 42))}…</span>` },
          ],
          empty: { title: '没有匹配的冲突', hint: '调整筛选条件，或改一条口径后再跑校验。' },
        })}
      </section>`;

    const filters = view.querySelector('#conflict-filters');
    filters?.addEventListener('change', () => {
      state.severity = filters.querySelector('[name=severity]').value;
      state.kind = filters.querySelector('[name=kind]').value;
      conflictsPage.render(view, ctx);
    });
    view.querySelector('#export-conflicts')?.addEventListener('click', async () => {
      try {
        await api.download('/api/exports/conflicts.csv', 'conflicts.csv');
        toast('冲突与影响面 CSV 已下载');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const name = row.querySelector('b')?.textContent;
        const item = data.items.find((entry) => entry.name === name);
        if (item) openConflict(view, ctx, item);
      });
    });
  },
};

export default conflictsPage;
