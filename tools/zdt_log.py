"""知定堂星广：每条成片视频第一次被看到「通过」的日期（Reina 11/20：知定堂按成片完成算，不按交付日期、不按发布）。

表里没有成片通过的时间，「交付日期」是排期日，上周排的行常在这周才交片、才通过。所以每天跑的时候记一次：
现在通过、日志里还没有的视频，记成 D（昨天，看板的数据日），以后一直用这个日期。
键用视频文件名（tools/agency_read.js 的 files），没有文件名的用「第 N 行_i」。
日志放在 tools/agency_targets.json 的 zdt_pass_log 里（这个文件每天排期提交都会带上；目标只认日期键，不受影响）。
排期看板（agency_progress.py）和素材产出看板（output_build.py）都用它，两边的数一致。

11/20 第一次建日志时，已经通过的按文件名里的日期补（如 11.18、-1118-、261118，那天交的片），
文件名没日期的按交付日期；补出来晚于 D 的按 D。
"""
import datetime as dt, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, 'tools', 'agency_targets.json')
KEY = 'zdt_pass_log'


def file_day(name, T):
    s = name or ''
    for pat in (r'(?<!\d)20(\d{2})(1[0-2])(\d{2})(?!\d)', r'(?<!\d)(\d{2})(1[0-2])([0-3]\d)(?!\d)'):
        m = re.search(pat, s)
        if m:
            try:
                return dt.date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
    m = re.search(r'(?<![\d.])(1[0-2])\.([0-3]?\d)(?![\d])', s)
    if m:
        try:
            return dt.date(T.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    m = re.search(r'(?<!\d)(1[0-2])([0-3]\d)(?!\d)', s)
    if m:
        try:
            return dt.date(T.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    return None


def keys_of(x):
    """一行里每条视频的键和文件名。"""
    files = [f for f in (x.get('files') or []) if f]
    n = max(1, int(x.get('vid') or 0), len(files))
    out = []
    for i in range(n):
        out.append((files[i] if i < len(files) else f"第{x['r']}行_{i + 1}", files[i] if i < len(files) else ''))
    return out


def update(rows, T, parse_day, write=True):
    """返回 {键: 通过日期} 里现在还是「通过」的那些，以及每个键对应的行。"""
    D = T - dt.timedelta(days=1)
    store = json.load(open(LOG, encoding='utf-8')) if os.path.exists(LOG) else {}
    log = store.get(KEY, {})
    seed = not log
    cur = {}
    for x in rows:
        if '通过' not in (x.get('vst') or ''):
            continue
        for k, fname in keys_of(x):
            if k not in log:
                if seed:
                    d = file_day(fname, T) or parse_day(x.get('d'), T) or D
                    d = min(d, D)
                else:
                    d = D
                log[k] = d.isoformat()
            cur[k] = (log[k], x)
    if write:
        store[KEY] = dict(sorted(log.items()))
        json.dump(store, open(LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return cur
