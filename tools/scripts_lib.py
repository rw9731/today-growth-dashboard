"""素材脚本库：scripts/<素材ID>.json，每条素材读一次全片字幕，存下来给日报、周报反复用。

一条脚本的格式（看视频时写）：
{"id": "素材ID", "name": "素材名", "checked": "YYYY-MM-DD",
 "dur": 56,                        # 总时长（秒）
 "form": "口播",                   # 口播 / 剧情 / vlog / 录屏 / 混剪（以真人或 AI 角色对镜头说为主算口播）
 "hook": "客户需求全都堆在微信里",  # 开头第一句原话
 "hook_type": "痛点",              # 痛点（直接说麻烦）/ 冲突（两件事撞上、出状况）/ 结果（先给 Today 做完的结果）/ 提问 / 人设（先介绍自己）/ 其他
 "pain": "工作和孩子的通知都堆在微信里，重要的总漏",   # 一句话：讲的是谁的什么麻烦
 "today_at": 10,                   # Today（名字、App 界面或手机录屏）第一次出现在第几秒；没出现写 null
 "rec": [8, 40],                   # Today 界面或录屏的起止秒数；没有写 null
 "demo": "微信消息一键转发，自动整理成每日晨间清单，临近截止的置顶",  # 演示的是 Today 的哪一下
 "ending": "繁杂的信息整理交给 Today，把专注力留给自己",          # 结尾落在哪
 "lines": ["0 客户需求", "2 全都堆在微信里", "..."],              # 全片字幕，每格一行：「秒数 字幕」，重复的合并
 "note": "可选：看到的问题，比如字幕被打码、有平台水印"}
"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'scripts')
FORMS = ['口播', '剧情', 'vlog', '录屏', '混剪']
HOOKS = ['痛点', '冲突', '结果', '提问', '人设', '其他']


def load():
    out = {}
    for f in glob.glob(os.path.join(DIR, '*.json')):
        try:
            s = json.load(open(f))
        except Exception:
            continue
        if s.get('id'):
            out[str(s['id'])] = s
    return out


def summary(s):
    """给页面用的短版本。"""
    if not s:
        return None
    return {'hook': s.get('hook', ''), 'hook_type': s.get('hook_type', ''), 'form': s.get('form', ''),
            'dur': s.get('dur'), 'today_at': s.get('today_at'), 'demo': s.get('demo', ''), 'pain': s.get('pain', '')}


def bucket_today(t):
    if t is None:
        return '没出现'
    return '3 秒内' if t <= 3 else '4 到 8 秒' if t <= 8 else '9 到 15 秒' if t <= 15 else '15 秒以后'


def bucket_dur(d):
    if d is None:
        return ''
    return '30 秒内' if d <= 30 else '31 到 45 秒' if d <= 45 else '46 到 60 秒' if d <= 60 else '60 秒以上'


DIMS = [('today', 'Today 第几秒出现', bucket_today, ['3 秒内', '4 到 8 秒', '9 到 15 秒', '15 秒以后', '没出现']),
        ('hook_type', '开头怎么钩', None, HOOKS),
        ('form', '形式', None, FORMS),
        ('dur', '时长', bucket_dur, ['30 秒内', '31 到 45 秒', '46 到 60 秒', '60 秒以上'])]


def patterns(items, scripts, min_act=30):
    """items: [{'id', 'cost', 'act', 'ret'}]（cost 和 act 是同一批激活的，ret 是它们的次留人数）。
    按脚本特征分组算次留率和次留成本；只算有脚本、激活够的素材。"""
    rows = []
    for it in items:
        s = scripts.get(it['id'])
        if not s or it['act'] < min_act:
            continue
        rows.append((it, s))
    total_cost = sum(it['cost'] for it in items) or 1
    cov = sum(it['cost'] for it, _ in rows) / total_cost
    out = {'n': len(rows), 'coverage': cov, 'dims': []}
    for key, label, fn, order in DIMS:
        g = {}
        for it, s in rows:
            v = fn(s.get({'today': 'today_at', 'dur': 'dur'}.get(key, key))) if fn else (s.get(key) or '其他')
            if not v:
                continue
            x = g.setdefault(v, {'n': 0, 'cost': 0.0, 'act': 0.0, 'ret': 0.0})
            x['n'] += 1; x['cost'] += it['cost']; x['act'] += it['act']; x['ret'] += it['ret']
        groups = []
        for v in order + sorted(set(g) - set(order)):
            if v not in g:
                continue
            x = g[v]
            groups.append({'v': v, 'n': x['n'], 'cost': x['cost'], 'act': x['act'],
                           'rate': x['ret'] / x['act'] if x['act'] else None, 'cpr': x['cost'] / x['ret'] if x['ret'] else None})
        out['dims'].append({'key': key, 'label': label, 'groups': groups})
    return out
