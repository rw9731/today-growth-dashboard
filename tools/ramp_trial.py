"""素材被建和带量（试算，Reina 11/9）：每条素材投进了几个账户、在几个账户里跑起来、头几天带了多少量。

Usage (from the repo root):
  python3 tools/ramp_trial.py --sheet <投放数据_分日 dump> --acct notes/acct-by-material-<读数日>.json --end 2026-11-08 \
      --from 2026-10-27 --to 2026-11-05 --out topic/2026-11-09-material-ramp/index.html

--acct 是在巨量升级版工作台（组织 1878449164572746）视频分析的数据集 EBP_management_mid_analysis 里，按 天 × 素材ID × 账户
拉 stat_cost、show_cnt，在浏览器里汇总成每条素材一行：首次有展示日、有展示的账户数、有消耗的账户数、
在该账户首次展示后 3 天内花到 ¥100 / ¥300 的账户数、单账户 3 天最高消耗、累计消耗（只读）。

口径（试算，等 Reina 定）：
- 投放账户数 = 有展示的账户数。巨量单元层的数据这个登录拿不到，先用账户数近似「被建次数」（每个账户至少建了一个单元）。
- 账户跑起来率 = 首次展示后 3 天内花到 ¥100 的账户数 ÷ 投放账户数。
- 带量能力看投放数据表：首次消耗后 3 天、7 天累计消耗，单日最高，第几天第一次单日过 ¥1,000。
"""
import argparse, collections, datetime as dt, html, json, os, re, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import compute as C  # noqa: E402

D = dt.date.fromisoformat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--acct', required=True)
    ap.add_argument('--end', required=True)
    ap.add_argument('--from', dest='frm', required=True)
    ap.add_argument('--to', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    rows = C.load_rows(a.sheet)
    daily = collections.defaultdict(lambda: collections.defaultdict(float))
    info = {}
    for r in rows:
        if r['date'] <= a.end:
            daily[r['id']][r['date']] += r['cost']
            info.setdefault(r['id'], r)
    acct = {x['id']: x for x in json.load(open(a.acct))}
    links = json.load(open(os.path.join(HERE, 'links.json')))
    ucs = json.load(open(os.path.join(HERE, 'ucs.json')))
    tot_day = collections.defaultdict(float)
    for r in rows:
        tot_day[r['date']] += r['cost']

    mats = []
    for i, dd in daily.items():
        days = sorted(d for d, c in dd.items() if c > 0)
        if not days:
            continue
        up = C.up_day(i)
        if not (a.frm <= up <= a.to):
            continue
        f = days[0]
        obs = (D(a.end) - D(f)).days + 1
        seq = [dd.get((D(f) + dt.timedelta(k)).isoformat(), 0.0) for k in range(min(obs, 21))]
        r = info[i]
        x = acct.get(i, {})
        lk = links.get(i, {})
        mats.append({
            'id': i, 'name': r['name'], 'kind': C.kind_of(r['src'], r['track'], r['name'], i).split(' · ')[0],
            'uc': r['uc'], 'short': ucs.get(r['uc'], {}).get('short', ''), 'made': C.made_day(r['name']), 'up': C.up_time(i), 'first': f,
            'obs': obs, 'c3': round(sum(seq[:3])), 'c7': round(sum(seq[:7])) if obs >= 7 else None, 'peak': round(max(seq)),
            'd1k': next((k + 1 for k, c in enumerate(seq) if c >= 1000), None), 'tot': round(sum(dd.values())),
            'n_show': x.get('n_show', 0), 'n_spend': x.get('n_spend', 0), 'n100': x.get('n100', 0), 'n300': x.get('n300', 0),
            'max3': x.get('max3', 0), 'video': C.pick_video(lk), 'link': '' if lk.get('type') == '预览' else lk.get('link', ''),
            'link_type': lk.get('type', ''),
        })

    def summ(g):
        n = len(g)
        shown = [m for m in g if m['n_show']]
        s_show = sum(m['n_show'] for m in shown)
        return {
            'n': n, 'acc_mean': round(s_show / len(shown), 1) if shown else None,
            'acc_med': st.median([m['n_show'] for m in shown]) if shown else None,
            'pass': sum(m['n100'] for m in shown) / s_show if s_show else None,
            'any': sum(1 for m in g if m['n100'] > 0) / n if n else None,
            'c3_med': st.median([m['c3'] for m in g]) if g else None,
            'c3_per_acc': sum(m['c3'] for m in shown) / s_show if s_show else None,
            'k1': sum(1 for m in g if m['d1k']) / n if n else None,
            'c3_sum': sum(m['c3'] for m in g),
        }

    by_kind = collections.defaultdict(list)
    by_up = collections.defaultdict(list)
    for m in mats:
        by_kind[m['kind']].append(m)
        by_up[m['up'][:10]].append(m)
    kind_rows = [{'k': k, **summ(g)} for k, g in sorted(by_kind.items(), key=lambda x: -len(x[1])) if len(g) >= 5]
    up_rows = []
    for k in sorted(by_up):
        s = summ(by_up[k])
        win = [(D(k) + dt.timedelta(j)).isoformat() for j in range(3)]
        s['tot3'] = sum(tot_day.get(d, 0) for d in win)
        up_rows.append({'k': k, **s})
    lag_mu = collections.Counter((D(m['up'][:10]) - D(m['made'])).days for m in mats if m['made'])
    lag_uf = collections.Counter((D(m['first']) - D(m['up'][:10])).days for m in mats)
    allsum = summ(mats)
    data = {'meta': {'end': a.end, 'frm': a.frm, 'to': a.to, 'n': len(mats), 'built': dt.date.today().isoformat()},
            'all': allsum, 'kind': kind_rows, 'up': up_rows, 'lag_mu': sorted(lag_mu.items()), 'lag_uf': sorted(lag_uf.items()),
            'mats': mats, 'tot_day': {d: round(v) for d, v in sorted(tot_day.items()) if a.frm <= d <= a.end}}

    head = open(os.path.join(ROOT, 'topic', 'index.html'), encoding='utf-8').read()
    style = re.search(r'<style>(.*?)</style>', head, re.S).group(1)
    tpl = open(os.path.join(HERE, 'ramp_trial_template.html'), encoding='utf-8').read()
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    out = tpl.replace('{{STYLE}}', style).replace('{{DATA}}', blob)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'w', encoding='utf-8').write(out)
    print(json.dumps({'n': len(mats), 'all': {k: (round(v, 3) if isinstance(v, float) else v) for k, v in allsum.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
