import { api } from '../api.js';
import { session } from '../store.js';
import { BRAND } from '../config.js';
import { errorMessage, esc, toast } from '../ui.js';

export const loginPage = {
  async render(root, ctx) {
    root.className = 'login-host';
    root.innerHTML = `
      <div class="login">
        <section class="login-brief">
          <div class="eyebrow">${esc(BRAND.edition)} · 卡片柜</div>
          <h1>${esc(BRAND.title)}<br /><em>${esc(BRAND.short)}</em></h1>
          <p class="tagline">${esc(BRAND.loginLead)}</p>
          <div class="brief-points">
            ${BRAND.loginTabs
              .map(
                ([no, range, text]) =>
                  `<div class="brief-point"><i>${esc(no)} · ${esc(range)}</i><span>${esc(text)}</span></div>`,
              )
              .join('')}
          </div>
          <div class="eyebrow" style="margin-top:auto">${esc(BRAND.org)} · 内部工作台 · 抽取需登记</div>
        </section>
        <section class="login-form-wrap">
          <form class="login-card" id="login-form" novalidate>
            <div>
              <div class="eyebrow">CALL SLIP</div>
              <div class="brand">指标口径索书单</div>
              <div class="sub">用内部账号登录。三个演示账号权限不同，页面、按钮与导出入口都会随角色变化。</div>
            </div>
            <div class="field">
              <label for="email">邮箱 / CALL NO.</label>
              <input id="email" name="email" type="email" autocomplete="username" value="admin@${esc(BRAND.short)}.io" required />
            </div>
            <div class="field">
              <label for="password">密码</label>
              <input id="password" name="password" type="password" autocomplete="current-password" value="Demo@2026" required />
            </div>
            <div class="form-error" id="login-error" role="alert"></div>
            <button class="btn accent" id="login-submit" type="submit">调阅卡片柜</button>
            <div class="login-hint">
              演示账号（密码 <code>Demo@2026</code>）：<br />
              <code>admin@${esc(BRAND.short)}.io</code> 指标管理员 · <code>analyst@${esc(BRAND.short)}.io</code> 指标专员 ·
              <code>viewer@${esc(BRAND.short)}.io</code> 报表只读
            </div>
          </form>
        </section>
      </div>`;

    const form = root.querySelector('#login-form');
    const errorNode = root.querySelector('#login-error');
    const submit = root.querySelector('#login-submit');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorNode.textContent = '';
      submit.disabled = true;
      submit.textContent = '正在核对索书号…';
      try {
        const result = await api.post('/api/auth/login', {
          email: form.email.value.trim(),
          password: form.password.value,
        });
        session.set(result.access_token, result.user);
        toast(`欢迎回来，${result.user.display_name}`);
        location.hash = '#/overview';
        await ctx.reload();
      } catch (err) {
        errorNode.textContent = err.code === 'AUTH_INVALID' ? '账号或密码不正确' : errorMessage(err);
      } finally {
        submit.disabled = false;
        submit.textContent = '调阅卡片柜';
      }
    });
  },
};

export default loginPage;
