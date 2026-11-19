import {addDays, groupCapacity, loadWeeklyPlan, shortDate} from './weekly_plan.js';

const types = ['AI', '二创'];
const sum = values => values.reduce((a, b) => a + b, 0);
const remaining = n => n < 0 ? '超 ' + -n : String(n);

function updateCapacity(plan, reportDate) {
  const section = document.querySelector('.cap');
  if (!section) return;
  const days = Array.from({length: 7}, (_, i) => addDays(plan.week, i));
  const marks = new Map();
  for (const e of plan.entries) {
    if (!types.includes(e.t)) continue;
    const key = [e.g, e.t, e.d].join('|');
    marks.set(key, (marks.get(key) || 0) + Number(e.n || 0));
  }
  const count = (g, ts, day) => sum(ts.map(t => marks.get([g, t, day].join('|')) || 0));
  const setDay = (cell, day) => {
    cell.classList.toggle('c-past', day < reportDate);
    cell.classList.toggle('c-today', day === reportDate);
  };
  for (const [i, th] of [...section.querySelectorAll('th[data-cap-day]')].entries()) {
    setDay(th, days[i]);
    th.replaceChildren(shortDate(days[i]), document.createElement('br'), '周' + '一二三四五六日'[i]);
  }

  let all = 0;
  for (const card of section.querySelectorAll('.cap-card[data-cap-group]')) {
    const g = card.dataset.capGroup;
    const cap = groupCapacity(plan.source, g, plan.week);
    const groupTotal = sum(days.map(day => count(g, types, day)));
    const capacity = sum(Object.values(cap));
    all += groupTotal;
    const left = capacity - groupTotal;
    const big = card.querySelector('.cap-big b');
    big.textContent = remaining(left);
    big.classList.toggle('over', left < 0);
    card.querySelector('.cap-bar span').style.width = (capacity ? Math.min(100, groupTotal / capacity * 100) : 0) + '%';
    const parts = types.map(type => {
      const slack = (cap[type] || 0) - sum(days.map(day => count(g, [type], day)));
      return type + (slack < 0 ? ' 超了 ' + -slack : ' 还能排 ' + slack);
    });
    card.querySelector('.cap-sub').textContent = '已排 ' + groupTotal + ' / 本周产能 ' + capacity + '，' + parts.join('，');
    const progress = document.querySelector('[data-plan-progress="' + g + '"]');
    if (progress) progress.textContent = '本周已排 ' + groupTotal
      + (left < 0 ? '，比产能多 ' + -left : left > 0 ? '，比产能少 ' + left : '');
  }
  section.querySelector('[data-cap-total]').textContent = all;
  section.querySelector('[data-cap-note]').textContent = plan.source.cap_note || '';

  for (const row of section.querySelectorAll('tr[data-cap-group]')) {
    const ts = row.dataset.capKind === '合计' ? types : [row.dataset.capKind];
    const cap = groupCapacity(plan.source, row.dataset.capGroup, plan.week);
    const byDay = days.map(day => count(row.dataset.capGroup, ts, day));
    for (const [i, td] of [...row.querySelectorAll('[data-cap-day]')].entries()) {
      setDay(td, days[i]);
      td.querySelector('b').textContent = byDay[i];
    }
    const n = sum(byDay);
    const capacity = sum(ts.map(t => cap[t] || 0));
    row.querySelector('.c-sum b').textContent = n;
    row.querySelector('.c-sum small').textContent = ' / ' + capacity;
    row.querySelector('.c-left').textContent = remaining(capacity - n);
  }
}

export async function schedulePlan(reportDate) {
  const plan = await loadWeeklyPlan();
  updateCapacity(plan, reportDate);
  return plan;
}
