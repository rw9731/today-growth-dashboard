import {addDays, loadWeeklyPlan, shortDate} from './weekly_plan.js';

function fillCount(cell, item, n) {
  cell.textContent = n || '';
  if (!item) return;
  const detail = document.createElement('span');
  detail.className = 'sub';
  detail.textContent = [...item.types].map(([type, count]) => type + ' ' + count).join('、');
  cell.append(detail);
}

function updateMap(plan, tierOf) {
  const table = document.querySelector('#map table');
  const rows = new Map([...table.tBodies[0].querySelectorAll('tr[data-uc]')].map(row => [row.dataset.uc, row]));
  for (const u of plan.cases.keys()) {
    if (rows.has(u)) continue;
    const row = table.tBodies[0].insertRow();
    row.dataset.uc = u;
    row.insertCell().textContent = '未入库';
    const label = row.insertCell();
    label.className = 'uc';
    label.textContent = u + ' ' + (plan.source.UC_extra?.[u] || '');
    row.insertCell().colSpan = table.tHead.rows[0].cells.length - 3;
    const count = row.insertCell();
    count.className = 'num';
    count.dataset.planCount = '';
    rows.set(u, row);
  }
  const weak = [];
  for (const [u, row] of rows) {
    fillCount(row.querySelector('[data-plan-count]'), plan.cases.get(u), plan.counts[u]);
    const tier = row.querySelector('[data-plan-tier]');
    if (tier) tier.textContent = tierOf.has(u) ? ' · ' + tierOf.get(u) : '';
    if (plan.counts[u] && row.cells[0].textContent.trim() === '判弱') weak.push(u + ' ' + row.dataset.ucName);
  }
  document.getElementById('week-plan-weak').textContent = weak.join('、') || '无';
}

function bigrams(s) {
  const chars = Array.from(s);
  return new Set(chars.slice(1).map((c, i) => chars[i] + c));
}

function similarity(a, b) {
  const source = bigrams(a);
  if (!source.size) return 0;
  const target = bigrams(b);
  return [...source].filter(x => target.has(x)).length / source.size;
}

function byScene(scenes, entries) {
  const counts = new Map();
  for (const e of entries) {
    const text = e.sc || '';
    const direct = scenes.filter(s => similarity(s.label, text) >= 0.6);
    const best = scenes.reduce((top, pick) => {
      const score = similarity(text, pick.label + pick.description);
      return score > top.score ? {pick, score} : top;
    }, {pick: null, score: 0});
    const matched = direct.length ? direct : best.score >= 0.34 ? [best.pick] : [{id: '0'}];
    const n = Number(e.n);
    matched.forEach(({id}, i) => counts.set(id,
      (counts.get(id) || 0) + Math.floor(n / matched.length) + (i < n % matched.length ? 1 : 0)));
  }
  return counts;
}

function updateTimeline(plan) {
  const table = document.querySelector('#roadmap table');
  const header = table.tHead.rows[0];
  const body = table.tBodies[0];
  const dates = () => [...header.querySelectorAll('[data-week]')];
  if (!dates().some(th => th.dataset.week === plan.week)) {
    const th = document.createElement('th');
    th.className = 'tc';
    th.dataset.week = plan.week;
    header.insertBefore(th, dates().find(h => h.dataset.week > plan.week) || header.cells[header.cells.length - 2]);
  }
  const next = addDays(plan.week, 7);
  for (const th of dates()) {
    const week = th.dataset.week;
    th.classList.toggle('cur', week === plan.week);
    th.textContent = (week === plan.week ? '本周 ' : week === next ? '下周 ' : '') + shortDate(week) + ' 起';
  }

  function setCell(row, n) {
    let td = row.querySelector('td[data-week="' + plan.week + '"]');
    if (!td) {
      const after = [...row.querySelectorAll('td[data-week]')].find(c => c.dataset.week > plan.week);
      td = row.insertCell(after ? after.cellIndex : row.cells.length - 2);
      td.className = 'tc fut';
      td.dataset.week = plan.week;
      td.title = (row.dataset.uc || row.dataset.for) + ' 本周 ' + shortDate(plan.week) + ' 起';
    }
    row.querySelectorAll('td.cur').forEach(c => c.classList.remove('cur'));
    td.classList.add('cur');
    if (td.classList.contains('fut')) td.classList.toggle('has', Boolean(n));
    td.title = td.title.replace(/，排期 \d+ 条/, '').replace(/下周 (\d+\/\d+ 起)/, '本周 $1');
    td.querySelector('.pl')?.remove();
    if (n) {
      const pill = document.createElement('span');
      pill.className = 'pl';
      pill.textContent = '排 ' + n;
      const [base, ...lit] = td.title.split('；');
      td.title = [base + '，排期 ' + n + ' 条', ...lit].join('；');
      td.append(pill);
    }
  }

  function addBaseline(row) {
    for (const th of dates()) {
      const td = row.insertCell();
      td.className = 'tc emp';
      td.dataset.week = th.dataset.week;
      td.title = (row.dataset.uc || row.dataset.for) + ' ' + th.textContent;
    }
    row.insertCell().className = 'num';
    row.insertCell().className = 'num';
  }

  const scenarios = new Map();
  for (const row of body.querySelectorAll('tr[data-for][data-scene]')) {
    const u = row.dataset.for;
    if (!scenarios.has(u)) scenarios.set(u, []);
    scenarios.get(u).push(row);
  }
  const roots = new Map([...body.querySelectorAll('tr[data-uc]')].map(row => [row.dataset.uc, row]));
  for (const u of plan.cases.keys()) {
    if (roots.has(u)) continue;
    const row = body.insertRow();
    row.dataset.uc = u;
    row.insertCell().textContent = '未入库';
    row.insertCell().textContent = u + ' ' + (plan.source.UC_extra?.[u] || '');
    addBaseline(row);
    roots.set(u, row);
  }

  for (const [u, root] of roots) {
    setCell(root, plan.counts[u]);
    const rows = scenarios.get(u);
    if (!rows) continue;
    const scenes = rows.filter(row => row.dataset.scene !== '0').map(row => {
      const span = row.querySelector('[data-scene-label]');
      return {id: row.dataset.scene, label: span.textContent, description: span.title};
    });
    const counts = byScene(scenes, plan.cases.get(u)?.entries || []);
    if (counts.get('0') && !rows.some(row => row.dataset.scene === '0')) {
      const last = rows[rows.length - 1];
      const row = body.insertRow(last.sectionRowIndex + 1);
      row.className = 'scr';
      row.dataset.for = u;
      row.dataset.scene = '0';
      row.hidden = !root.classList.contains('open');
      row.insertCell().textContent = '其他';
      const name = row.insertCell();
      name.className = 'uc sc';
      name.textContent = '没对上场景';
      addBaseline(row);
      rows.push(row);
    }
    for (const row of rows) setCell(row, counts.get(row.dataset.scene));
  }
}

async function refresh() {
  let plan;
  try {
    plan = await loadWeeklyPlan();
  } catch {
    document.querySelector('[data-plan-status]').hidden = false;
    return;
  }
  const groups = plan.source.GROUPS || [];
  const tierOf = new Map(groups.flatMap(([title, us]) => us.map(u => [u, title])));
  const tiers = new Map();
  for (const [u, n] of Object.entries(plan.counts)) {
    const title = tierOf.get(u) || '没分档';
    tiers.set(title, (tiers.get(title) || 0) + n);
  }
  const summary = document.getElementById('week-plan-summary');
  summary.querySelector('b').textContent = '本周已排 ' + plan.total + ' 条（' + shortDate(plan.week) + '–' + shortDate(plan.end) + '）';
  const parts = plan.total ? groups.map(([title,, target]) => {
    const n = tiers.get(title) || 0;
    return title + ' ' + n + ' 条（' + Math.round(n / plan.total * 100) + '%，目标 ' + target + '%）';
  }) : ['这周还没有排期'];
  if (tiers.get('没分档')) parts.push('没分档 ' + tiers.get('没分档') + ' 条');
  summary.querySelector('span').textContent = parts.join('、');
  updateMap(plan, tierOf);
  updateTimeline(plan);
}
await refresh();
