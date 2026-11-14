import { api } from '../api.js';
import { ENUMS, can, parseTone } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, filterBar, fmtTime, kv, parseGrid, table, toast } from '../ui.js';

const state = { q: '', domain: '', tier: '', status: '' };

const DOMAIN_OPTIONS = [{ value: '', label: '全部业务域' }, ...Object.entries(ENUMS.metricDomain).map(([value, label]) => ({ value, label }))];
const TIER_OPTIONS = [{ value: '', label: '全部分级' }, ...Object.entries(ENUMS.metricTier).map(([value, label]) => ({ value, label }))];
const STATUS_OPTIONS = [{ value: '', label: '全部状态' }, ...Object.entries(ENUMS.metricStatus).map(([value, label]) => ({ value, label }))];

function openDetail(view, ctx, item) {
  const editable = can(ctx.user.role, 'formula:write');
  return api
    .get(`/api/metrics/${item.id}`)
    .then((detail) => {
      const metric = detail.metric;
      const { root, close } = drawer({
        title: `${metric.name} · ${metric.code}`,
        subtitle: `${metric.domain_label} / ${metric.tier_label} / 版本 v${metric.current_version}`,
        body: `
          ${kv([
            ['指标编码', `<span class="mono">${esc(metric.code)}</span>`],
            ['业务域', esc(metric.domain_label)],
            ['分级', `<span class="badge ${metric.tier === 'core' ? 'high' : 'info'}">${esc(metric.tier_label)}</span>`],
            ['单位 / 负责人', `${esc(metric.unit)} · ${esc(metric.owner)}`],
            ['解析状态', `<span class="badge ${parseTone(metric.parse_status)}">${esc(ENUMS.parseStatus[metric.parse_status] || metric.parse_status)}</span>`],
            ['依赖指标', (metric.deps || []).length ? esc(metric.deps.join(' / ')) : '—'],
            ['下游报表', (metric.reports || []).length ? esc(metric.reports.join(' / ')) : '—'],
            ['更新时间', fmtTime(metric.updated_at)],
            ['说明', esc(metric.description || '—')],
          ])}
          <div class="dsl-box">
            <span class="label">口径 DSL · v${esc(metric.current_version)}</span>
            <pre class="code">${esc(metric.dsl_text || '（无）')}</pre>
          </div>
          <div class="dsl-box">
            <span class="label">算法 A · 解析结果</span>
            ${parseGrid(metric)}
            ${metric.parse_error ? `<pre class="code"><span class="err">${esc(metric.parse_error)}</span></pre>` : ''}
          </div>
          <div class="dsl-box">
            <span class="label">版本历史（${(detail.history || []).length} 条）</span>
            <div class="list-tight">
              ${(detail.history || [])
                .map(
                  (row) =>
                    `<div class="impact-row"><span class="mono">v${esc(row.version)} · ${esc(row.author_email)}</span><span class="muted tiny">${fmtTime(row.created_at)} · ${esc(ENUMS.parseStatus[row.parse_status] || row.parse_status)}</span></div>`,
                )
                .join('')}
            </div>
          </div>
          ${
            editable
              ? `<div class="dsl-box" id="dsl-editor">
                  <span class="label">改口径 → 先解析，再决定是否保存新版本</span>
                  ${field({ label: 'DSL 文本', name: 'dsl_text', value: metric.dsl_text })}
                  <div style="display:flex;gap:8px;flex-wrap:wrap">
                    <button class="btn sm ghost" id="parse-btn" type="button">解析预览</button>
                    <button class="btn sm accent" id="save-dsl" type="button">保存为新版本</button>
                  </div>
                  <div id="parse-result"></div>
                </div>`
              : '<p class="muted tiny">只读角色可以查看口径与解析结果，不能改口径。</p>'
          }`,
      });

      if (!editable) return;
      const input = root.querySelector('[name=dsl_text]');
      const resultBox = root.querySelector('#parse-result');
      const renderParse = (parsed) => {
        if (parsed.status === 'ok') {
          resultBox.innerHTML = `${parseGrid(parsed)}<p class="tiny muted" style="margin-top:6px">表达式：${esc(parsed.expression || '')}</p>`;
        } else {
          const error = parsed.error || {};
          resultBox.innerHTML = `<pre class="code"><span class="err">${esc(`${error.code} · 第 ${error.column} 列：${error.message}`)}</span>
${esc(error.snippet || '')}</pre>`;
        }
      };
      root.querySelector('#parse-btn')?.addEventListener('click', async () => {
        try {
          const parsed = await api.post(`/api/metrics/${metric.id}/parse`, { dsl_text: input.value });
          renderParse(parsed);
          toast(parsed.status === 'ok' ? '解析通过' : '解析失败，已标出位置', parsed.status === 'ok' ? '' : 'err');
        } catch (err) {
          toast(errorMessage(err), 'err');
        }
      });
      root.querySelector('#save-dsl')?.addEventListener('click', async () => {
        try {
          await api.post(`/api/metrics/${metric.id}/formulas`, { dsl_text: input.value, note: '页面编辑' });
          toast('已保存为新的口径版本');
          close();
          await metricsPage.render(view, ctx);
        } catch (err) {
          const detail = err.detail || {};
          if (err.code === 'VALIDATION' && detail.code) {
            resultBox.innerHTML = `<pre class="code"><span class="err">${esc(`${detail.code} · 第 ${detail.column} 列：${detail.message}`)}</span>
${esc(detail.snippet || '')}</pre>`;
          } else {
            toast(errorMessage(err), 'err');
          }
        }
      });
    })
    .catch((err) => toast(errorMessage(err), 'err'));
}

function openCreate(view, ctx) {
  const { root, close } = drawer({
    title: '注册新指标',
    subtitle: '登记口径后立刻跑一次算法 A 解析',
    body: `<form id="metric-form" class="form-grid" style="display:grid;gap:12px">
      ${field({ label: '指标编码（小写 / 数字 / 下划线）', name: 'code', placeholder: 'gmv_net_v2' })}
      ${field({ label: '指标名称（同名会被冲突检测分组）', name: 'name', placeholder: 'GMV' })}
      ${field({ label: '业务域', name: 'domain', value: 'trade', options: Object.entries(ENUMS.metricDomain).map(([value, label]) => ({ value, label })) })}
      ${field({ label: '分级', name: 'tier', value: 'normal', options: Object.entries(ENUMS.metricTier).map(([value, label]) => ({ value, label })) })}
      ${field({ label: '单位', name: 'unit', value: '元' })}
      ${field({ label: '负责人', name: 'owner', value: '林可' })}
      ${field({ label: '口径 DSL', name: 'dsl_text', placeholder: "x = sum(dwd.order.amount) where order_status = 'paid' group by dt" })}
      <div class="form-error" id="metric-error"></div>
      <button class="btn accent" type="submit">保存并解析</button>
    </form>`,
  });
  root.querySelector('#metric-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.post('/api/metrics', {
        code: form.code.value.trim(),
        name: form.name.value.trim(),
        domain: form.domain.value,
        tier: form.tier.value,
        unit: form.unit.value.trim() || '元',
        owner: form.owner.value.trim() || null,
        dsl_text: form.dsl_text.value.trim() || null,
      });
      toast('指标已登记');
      close();
      await metricsPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#metric-error').textContent =
        err.code === 'CONFLICT' ? '指标编码已存在，请换一个' : errorMessage(err);
    }
  });
}

export const metricsPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/metrics', {
        q: state.q,
        domain: state.domain,
        tier: state.tier,
        status: state.status,
        limit: 100,
      });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => metricsPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>指标注册目录</h2>
          <div style="display:flex;gap:10px;align-items:center">
            <span class="meta">${data.total} 条</span>
            ${can(ctx.user.role, 'metric:write') ? '<button class="btn sm accent" id="new-metric">注册指标</button>' : ''}
          </div>
        </div>
        ${filterBar('metric-filters', [
          { label: '搜索', name: 'q', value: state.q, placeholder: '编码 / 名称' },
          { label: '业务域', name: 'domain', value: state.domain, options: DOMAIN_OPTIONS },
          { label: '分级', name: 'tier', value: state.tier, options: TIER_OPTIONS },
          { label: '状态', name: 'status', value: state.status, options: STATUS_OPTIONS },
        ])}
        ${table({
          rows: data.items,
          columns: [
            { key: 'code', label: '索引号', className: 'mono', render: (row) => `<span class="index-tag">${esc(row.code)}</span>` },
            { key: 'name', label: '指标名称', render: (row) => `<b>${esc(row.name)}</b>` },
            { key: 'domain_label', label: '业务域' },
            { key: 'tier_label', label: '分级', render: (row) => `<span class="badge ${row.tier === 'core' ? 'high' : 'info'}">${esc(row.tier_label)}</span>` },
            { key: 'current_version', label: '版本', className: 'num', render: (row) => `v${esc(row.current_version)}` },
            {
              key: 'parse_status',
              label: '解析',
              render: (row) => `<span class="badge ${parseTone(row.parse_status)}">${esc(ENUMS.parseStatus[row.parse_status] || row.parse_status)}</span>`,
            },
            { key: 'deps', label: '依赖', className: 'mono', render: (row) => esc((row.deps || []).join(' / ') || '—') },
            { key: 'report_count', label: '下游报表', className: 'num' },
            { key: 'owner', label: '负责人' },
            { key: 'updated_at', label: '更新时间', render: (row) => `<span class="tiny">${fmtTime(row.updated_at)}</span>` },
          ],
          empty: { title: '没有匹配的指标', hint: '换一个筛选条件，或由管理员注册新指标。' },
        })}
      </section>`;

    const filters = view.querySelector('#metric-filters');
    filters?.addEventListener('change', () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.domain = filters.querySelector('[name=domain]').value;
      state.tier = filters.querySelector('[name=tier]').value;
      state.status = filters.querySelector('[name=status]').value;
      metricsPage.render(view, ctx);
    });
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        state.q = event.target.value.trim();
        metricsPage.render(view, ctx);
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openDetail(view, ctx, item);
      });
    });
    view.querySelector('#new-metric')?.addEventListener('click', () => openCreate(view, ctx));
  },
};

export default metricsPage;
