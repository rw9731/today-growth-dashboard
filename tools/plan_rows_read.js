// 排期数据对表：读扩量排期这一周的行（只读），给 tools/plan_sync.py 用（Reina 11/12：飞书排期改了，plan 的 E 要一起改）。
// 在 A 组 kMJdAv、B 组 3KtioB 页面跑全文，返回的 JSON 原样存成 /tmp/sync/<tab id>.json。
let __sh = null;
for (let i = 0; i < 60; i++) { try { __sh = window.spread && window.spread.getActiveSheet(); if (__sh && __sh.getText(0, 1)) break; } catch (e) { /* 还没加载 */ } __sh = null; await new Promise((r) => setTimeout(r, 500)); }
if (!__sh) throw new Error('sheet 没加载');
const __H = []; for (let c = 0; c < __sh.getColumnCount(); c++) __H.push((__sh.getText(0, c) || '').trim());
const __c = (w) => { const i = __H.findIndex((h) => h === w || h.startsWith(w)); return i; };
const C = { uc: __c('UC_ID'), sc: __c('细分场景'), t: __c('素材类型'), basis: __c('依据'), n: __c('条数'), how: __c('怎么改'), src: __c('来源') };
const __t = (r, c) => (c < 0 ? '' : (__sh.getText(r, c) || '').trim());
const rows = [];
let day = '';
for (let r = 1; r < __sh.getRowCount(); r++) {
  const d = __t(r, 0); if (d) day = d.split('\n')[0];
  const uc = __t(r, C.uc), n = __t(r, C.n);
  if (!uc && !n) continue;
  const how = __t(r, C.how);
  rows.push({ r: r + 1, d0: d.slice(0, 20), day: day.slice(0, 20), uc: uc.split('\n')[0].slice(0, 8), n, t: __t(r, C.t).slice(0, 12), sc: __t(r, C.sc).split(/[：:；;\n]/)[0].slice(0, 30), basis: __t(r, C.basis).slice(0, 40), how: how.split('\n')[0].slice(0, 120), tm: ((how.match(/(?:集中做|照)「([^」]+)」/) || [])[1] || '').slice(0, 60), same: /同脚本换画面/.test(how) ? 1 : 0, src: __t(r, C.src).slice(0, 10) });
}
JSON.stringify({ sheet: __sh.id(), rows });
