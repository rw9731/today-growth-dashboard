/**
 * 巨量 3 留、7 留回刷（Reina 11/27）
 * 巨量的 3 日、7 日留存改成和 Daily Insight 一样的口径（第 N 天当天回来），回刷到 11/16 前后激活的人。
 * 7 留要激活后第 7 天过完才有，原来的日更只刷最近 5 天、也没拉 7 日留存，所以单独加这个：
 * 每天 13 点多（避开 5 点的日更和上午的看板任务）把最近 12 天（T-12 到 T-1）每条素材的 3 日留存、7 日留存重新拉一遍，写进「投放数据_分日」AB（3日留存）和 AC（7日留存）。
 * 只读巨量，不改任何投放；不动 A:N，也不动日更脚本。和日更放在同一个 Apps Script 项目里（新建一个文件贴进去），共用它的工具函数和 OE_TOKEN。
 *
 * 安装：扩展程序 → Apps Script → 左边「文件」旁的 + → 脚本，命名 jl_ret_sync，把这整段贴进去保存；
 * 然后在上方函数下拉里选 setupRet 运行一次：建每天 13 点的触发器，并马上从 2026-11-10 回刷到昨天（约 20 到 40 分钟，自己续跑）。
 * 运行记录写在隐藏 tab「_巨量同步」，状态列是 ret。
 */

const RET_TAB = '_巨量留存';
const RET_BACKFILL_FROM = '2026-11-10';
const RET_DAYS = 12;
const RET_HOUR = 13;
const RET_DIMS = ['stat_time_day', 'material_id', 'image_mode'];
const RET_METRICS = ['attribution_convert_cnt', 'attribution_retention_3d_cnt', 'attribution_retention_7d_cnt'];

function setupRet() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (['retDaily', 'retWork', 'retResume'].includes(t.getHandlerFunction())) ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('retDaily').timeBased().atHour(RET_HOUR).everyDays(1).inTimezone(TZ).create();
  log_('ret', '已建每天 ' + RET_HOUR + ' 点的 3 留、7 留回刷触发器；开始从 ' + RET_BACKFILL_FROM + ' 回刷');
  retBackfill();
}

/** 每天：T-12 到 T-1 */
function retDaily() {
  const T = parse_(ymd_(new Date()));
  retStart_(ymd_(addDays_(T, -RET_DAYS)), ymd_(addDays_(T, -1)));
}

/** 一次性：从 RET_BACKFILL_FROM 回刷到昨天 */
function retBackfill() {
  retStart_(RET_BACKFILL_FROM, ymd_(addDays_(parse_(ymd_(new Date())), -1)));
}

function retResume() {
  deleteTriggers_('retResume');
  const p = JSON.parse(PropertiesService.getScriptProperties().getProperty('RETPEND') || 'null');
  if (p) retStart_(p.from, p.to);
}

function retStart_(from, to) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) {  // 日更还在跑：10 分钟后再来
    PropertiesService.getScriptProperties().setProperty('RETPEND', JSON.stringify({ from: from, to: to }));
    ScriptApp.newTrigger('retResume').timeBased().after(10 * 60 * 1000).create();
    return;
  }
  try {
    const job = { from: from, to: to, idx: 0, fails: [], failReqs: [], redo: [], round: 0, startedAt: now_(), refreshed: false };
    const accs = loadAccounts_(false);
    job.nAcc = accs.list.length;
    const sh = sh_(RET_TAB);
    sh.clearContents();
    sh.getRange('A:C').setNumberFormat('@');
    sh.getRange(1, 1, 1, 5).setValues([['日期', '平台', '素材ID', '3日留存', '7日留存']]);
    PropertiesService.getScriptProperties().setProperty('RETJOB', JSON.stringify(job));
    log_('ret', '开始拉 ' + from + ' 到 ' + to + ' 的 3 留、7 留：' + job.nAcc + ' 个户');
  } finally {
    lock.releaseLock();
  }
  retWork();
}

function retWork() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) { ScriptApp.newTrigger('retWork').timeBased().after(5 * 60 * 1000).create(); return; }
  const t0 = Date.now();
  const pr = PropertiesService.getScriptProperties();
  try {
    deleteTriggers_('retWork');
    const job = JSON.parse(pr.getProperty('RETJOB') || 'null');
    if (!job || job.done) return;
    const accs = loadAccounts_(false).list;
    const sh = sh_(RET_TAB);
    job.failReqs = job.failReqs || []; job.redo = job.redo || [];
    // 补拉上一轮被限频的请求（Reina 11/27：日更回填同时在跑会抢频率，失败的隔 10 分钟再拉，最多 3 轮）
    while (job.redo.length) {
      if (Date.now() - t0 > MAX_MS) { saveJob_(pr, job); ScriptApp.newTrigger('retWork').timeBased().after(60 * 1000).create(); return; }
      const part = job.redo.splice(0, CHUNK * 2);
      const rows = retPull_(null, job, part.map(f => ({ acc: [f[0], f[1]], topic: f[2] === 'S' ? 'STD_MATERIAL_DATA' : 'MATERIAL_DATA', page: f[3], n: 0 })));
      if (job.tokenDead) { job.done = true; saveJob_(pr, job); log_('ret', 'token 失效，3 留、7 留没刷：' + job.tokenDead); return; }
      if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, 5).setValues(rows);
      Utilities.sleep(300);
    }
    while (job.idx < accs.length) {
      if (Date.now() - t0 > MAX_MS) {
        saveJob_(pr, job);
        ScriptApp.newTrigger('retWork').timeBased().after(60 * 1000).create();
        return;
      }
      const batch = accs.slice(job.idx, job.idx + CHUNK);
      const rows = retPull_(batch, job);
      if (job.tokenDead) {
        job.done = true; pr.setProperty('RETJOB', JSON.stringify(job));
        log_('ret', 'token 失效，3 留、7 留没刷：' + job.tokenDead);
        mail_('巨量 3 留、7 留回刷：token 失效', job.tokenDead);
        return;
      }
      if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, 5).setValues(rows);
      job.idx += batch.length;
      Utilities.sleep(300);
    }
    if (job.failReqs.length && job.round < 3) {  // 有被限频的：10 分钟后只补拉这些
      job.round++;
      if (job.failReqs.length > 200) {  // 失败太多（脚本属性存不下），整段重拉
        log_('ret', job.failReqs.length + ' 个请求没拉到（多是限频），15 分钟后第 ' + job.round + ' 轮整段重拉');
        job.idx = 0; job.failReqs = []; job.fails = []; job.redo = [];
        sh.getRange(2, 1, Math.max(sh.getLastRow() - 1, 1), 5).clearContent();
        saveJob_(pr, job);
        ScriptApp.newTrigger('retWork').timeBased().after(15 * 60 * 1000).create();
        return;
      }
      log_('ret', '主循环拉完，' + job.failReqs.length + ' 个请求没拉到（多是限频），10 分钟后第 ' + job.round + ' 轮补拉');
      job.redo = job.failReqs; job.failReqs = []; job.fails = [];
      saveJob_(pr, job);
      ScriptApp.newTrigger('retWork').timeBased().after(10 * 60 * 1000).create();
      return;
    }
    if (Date.now() - t0 > 2.5 * 60000) {  // 写表单独放一次执行
      job.pulled = true;
      saveJob_(pr, job);
      ScriptApp.newTrigger('retWork').timeBased().after(60 * 1000).create();
      return;
    }
    retWrite_(job);
    job.done = true;
    saveJob_(pr, job);
  } catch (e) {
    log_('ret', '脚本出错：' + (e && e.stack ? e.stack : e));
    mail_('巨量 3 留、7 留回刷：脚本出错', String(e && e.stack ? e.stack : e));
  } finally {
    lock.releaseLock();
  }
}

/** 拉一批户（两个主题，翻页取全），返回 [日期, 平台, 素材ID, 3日留存, 7日留存]，排除「标题」和两个都是 0 的 */
function failKey_(r) {
  return [r.acc[0], /安卓/.test(r.acc[1]) ? '安卓' : 'iOS', r.topic === 'STD_MATERIAL_DATA' ? 'S' : 'M', r.page];
}

function saveJob_(pr, job) {
  pr.setProperty('RETJOB', JSON.stringify({ ...job, fails: job.fails.slice(0, 40) }));
}

function retPull_(batch, job, given) {
  let reqs = given || [];
  if (batch) batch.forEach(a => ['STD_MATERIAL_DATA', 'MATERIAL_DATA'].forEach(tp => reqs.push({ acc: a, topic: tp, page: 1, n: 0 })));
  const out = [];
  for (let loop = 0; reqs.length && loop < 40; loop++) {
    const resps = UrlFetchApp.fetchAll(reqs.map(r => ({ url: retUrl_(r.acc[0], r.topic, job.from, job.to, r.page), method: 'get',
      muteHttpExceptions: true, headers: { 'Access-Token': token_() } })));
    const next = [];
    let wait = 0;
    resps.forEach((resp, i) => {
      const r = reqs[i];
      let res;
      try { res = parseJson_(resp.getContentText()); } catch (e) { res = { code: -1, message: 'HTTP ' + resp.getResponseCode() }; }
      if (res.code === 0) {
        const d = res.data || {};
        (d.rows || []).forEach(row => {
          const dm = row.dimensions || {}, m = row.metrics || {};
          if (dm.image_mode === '标题') return;
          const r3 = num_(m.attribution_retention_3d_cnt), r7 = num_(m.attribution_retention_7d_cnt);
          if (!r3 && !r7) return;
          out.push([dm.stat_time_day, /安卓/.test(r.acc[1]) ? '安卓' : 'iOS', String(dm.material_id), r3, r7]);
        });
        const tp = (d.page_info && d.page_info.total_page) || 0;
        if (r.page === 1) for (let p = 2; p <= tp; p++) next.push({ acc: r.acc, topic: r.topic, page: p, n: 0 });
      } else if (isTokenErr_(res)) {
        if (!job.refreshed && refreshToken_()) { job.refreshed = true; next.push(r); }
        else job.tokenDead = res.code + ' ' + (res.message || '');
      } else if (r.n < (isRateErr_(res) ? 6 : 3)) {
        r.n++; next.push(r); wait = Math.max(wait, isRateErr_(res) ? 3000 * r.n : 2000);
      } else {
        job.fails.push(r.acc[0] + ' ' + r.acc[1] + ' ' + r.topic + ' p' + r.page + '：' + res.code + ' ' + (res.message || ''));
        job.failReqs.push(failKey_(r));
      }
    });
    if (job.tokenDead) return out;
    if (wait) Utilities.sleep(wait);
    reqs = next;
  }
  reqs.forEach(r => { job.fails.push(r.acc[0] + ' ' + r.topic + ' p' + r.page + '：重试后仍失败'); job.failReqs.push(failKey_(r)); });
  return out;
}

function retUrl_(advId, topic, start, end, page) {
  const q = {
    advertiser_id: advId, data_topic: topic, dimensions: JSON.stringify(RET_DIMS), metrics: JSON.stringify(RET_METRICS),
    filters: '[]', start_time: start + ' 00:00:00', end_time: end + ' 23:59:59',
    order_by: JSON.stringify([{ field: 'attribution_convert_cnt', type: 'DESC' }]), page: page, page_size: 100
  };
  return API + '/v3.0/report/custom/get/?' + Object.keys(q).map(k => k + '=' + encodeURIComponent(q[k])).join('&');
}

/** 汇总后写 AB（3日留存）、AC（7日留存）：from 到 to 的每一行都重写，没拉到的写 0 */
function retWrite_(job) {
  if (job.fails.length) {
    // 有户没拉到就不覆盖（免得把已有的数写成 0），下次再刷
    log_('ret', '有 ' + job.fails.length + ' 个请求失败，没写表：' + job.fails.slice(0, 10).join('；'));
    mail_('巨量 3 留、7 留回刷：有户没拉到，没写表', job.fails.join('\n'));
    return;
  }
  const ss = SpreadsheetApp.getActive();
  const stz = ss.getSpreadsheetTimeZone();
  const sd = x => x instanceof Date ? Utilities.formatDate(x, stz, 'yyyy-MM-dd') : String(x).replace(/^'/, '');
  const agg = {}, tot = {};
  const src = sh_(RET_TAB);
  if (src.getLastRow() > 1) src.getRange(2, 1, src.getLastRow() - 1, 5).getValues().forEach(r => {
    const d = sd(r[0]);
    const k = d + '|' + r[1] + '|' + String(r[2]).replace(/^'/, '');
    const v = agg[k] || (agg[k] = [0, 0]);
    v[0] += Number(r[3]) || 0; v[1] += Number(r[4]) || 0;
    const t = tot[d] || (tot[d] = [0, 0]); t[0] += Number(r[3]) || 0; t[1] += Number(r[4]) || 0;
  });
  const sh = ss.getSheetByName(TAB_DATA);
  const last = sh.getLastRow();
  const ds = sh.getRange(1, 1, last, 1).getValues().map(r => sd(r[0]));
  let r0 = ds.findIndex((x, i) => i > 0 && x >= job.from) + 1;
  if (r0 === 0) { log_('ret', '表里没有 ' + job.from + ' 以后的行'); return; }
  const keys = sh.getRange(r0, 1, last - r0 + 1, 3).getValues();
  let n3 = 0, n7 = 0, hit = 0;
  const vals = keys.map(r => {
    const d = sd(r[0]);
    if (d > job.to) return [null, null];
    const v = agg[d + '|' + r[1] + '|' + String(r[2]).replace(/^'/, '')];
    if (v) hit++;
    const a = v ? Math.round(v[0]) : 0, b = v ? Math.round(v[1]) : 0;
    if (a) n3++; if (b) n7++;
    return [a, b];
  });
  // 只写 from 到 to 的行（to 以后的行原样不动）
  let n = vals.findIndex(v => v[0] === null); if (n === -1) n = vals.length;
  if (n) sh.getRange(r0, 28, n, 2).setValues(vals.slice(0, n));
  if (sh.getRange(1, 29).getValue() !== '7日留存') sh.getRange(1, 29).setValue('7日留存');
  const miss = Object.keys(agg).length - hit;
  const byDay = Object.keys(tot).sort().map(d => d.slice(5) + ' 3留 ' + Math.round(tot[d][0]) + ' 7留 ' + Math.round(tot[d][1])).join('，');
  log_('ret', '已写 ' + job.from + ' 到 ' + job.to + ' 共 ' + n + ' 行（第 ' + r0 + ' 行起）：3日留存有值 ' + n3 + ' 行、7日留存有值 ' + n7 +
    ' 行；巨量有、表里没有这一行的 ' + miss + ' 条；分天合计：' + byDay);
}
