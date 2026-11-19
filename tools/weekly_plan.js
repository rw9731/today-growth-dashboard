export function addDays(iso, days) {
  const date = new Date(iso + 'T00:00:00Z');
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function shortDate(iso) {
  return Number(iso.slice(5, 7)) + '/' + Number(iso.slice(8, 10));
}

export function groupCapacity(source, group, week) {
  const cap = source.cap_day?.[group];
  if (!cap) return {};
  const extra = source.cap_extra?.[week]?.[group] || {};
  return Object.fromEntries(['AI', '二创'].map(type => [
    type, 5 * (cap.wd[type] || 0) + 2 * (cap.we[type] || 0) + Number(extra[type] || 0),
  ]));
}

export function summarizePlan(source) {
  const week = source.week;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(week) || !Array.isArray(source.E)) {
    throw new Error('排期数据缺少周次或条目');
  }
  const end = addDays(week, 6);
  const entries = source.E.filter(e =>
    week <= e.d && e.d <= end && e.s !== 'cut' && !String(e.to || '').includes('顺延')
  );
  const cases = new Map();
  const counts = Object.create(null);
  let total = 0;
  for (const e of entries) {
    const n = Number(e.n || 0);
    if (!e.uc || !Number.isSafeInteger(n) || n < 0) throw new Error('排期条目含无效数量或 use case');
    if (!n) continue;
    if (!cases.has(e.uc)) cases.set(e.uc, {types: new Map(), entries: []});
    const item = cases.get(e.uc);
    item.types.set(e.t || '', (item.types.get(e.t || '') || 0) + n);
    item.entries.push(e);
    counts[e.uc] = (counts[e.uc] || 0) + n;
    total += n;
  }
  return {source, week, end, entries, cases, counts, total};
}

export async function loadWeeklyPlan() {
  const response = await fetch(new URL('./schedule_plan.json', import.meta.url), {
    cache: 'no-store', signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error('排期同步请求失败');
  return summarizePlan(await response.json());
}
