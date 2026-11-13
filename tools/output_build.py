"""素材产出看板（Reina 11/10）：两组每天交的素材统一放一处，按「头部模板变式 / 新测试」等维度看，每条都带链接。

用法：
  python3 tools/output_build.py --dir <output_read.js 结果目录> --date T [--sheet <投放数据_分日 文件>]

- <dir> 里是 tools/output_read.js 在 5 个 tab 上跑出来的 <tab id>.tsv（每行一条：组 表 行号 成片列 日期 UC 细分场景 分类 AI/二创 素材名）。
- 结果累积在 notes/output-items.json（同一条素材按组+名字去重，重读会覆盖），页面写 output/index.html 和 output/<这周周一>/index.html，目录 outputs.json。
- 分类：V 头部模板变式、S 同脚本换画面（也算变式）、N 新测试、X 只换前贴（不计数）。表里排期行写了「头部模板」的算 V；名字里带 22 个头部模板原片标识的也算 V。
- 外部 agency（Reina 11/13）：--agency 目录里的知定堂、悦普，--kv 的 AnyMedia，见 agency()。页面「类型」放最前面（AI、二创、星广、抖音星图、抖音达人、小红书达人），「来源」替代原来的「组」（唯西 A 组、唯西 B 组、知定堂、悦普、AnyMedia）。
- 链接：飞书成片那一格（?sheet=…&range=列行的 base64），已经投出去的再带巨量视频（tools/links.json，按素材名在分日表找素材 ID）。
"""
import argparse, base64, datetime as dt, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = {'A': 'https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc', 'B': 'https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb'}
TABS = {'kMJdAv': 'A 组扩量排期', 'f18d7b': 'A 组脚本及成片', '3KtioB': 'B 组扩量排期', 'c665d9': 'B 组脚本&成片', 'EnYgPG': 'B 组二剪'}
TAB_RANK = {'kMJdAv': 0, '3KtioB': 0, 'f18d7b': 1, 'c665d9': 1, 'EnYgPG': 1}
# 「头部素材结构提取和变式（11/9）」22 个模板的原片标识，名字里带这些的算头部模板变式
TEMPLATE_KEYS = ['英语口语陪练与个性化带学', '在微信里直接跟Today对话', '恩泽哥哥和贝拉妹妹', 'W11-ljq-01', '约多人会议：查空档', 'NT01-说来惭愧',
                 'W01-zl-07', '开完会整理行动项', '整理电子发票和差旅报销_01', 'H08_neko', 'A18-06', '提前协调工作与接娃安排_01',
                 '每天一张卡看清日程和待办_01', 'L06-05', '找出工作邮箱里遗漏的重要邮件', '个性化读书与自我提升计划_02', 'LG01-03-zl',
                 'A05-03', 'M01-05', '按训练和做饭时间安排一日三餐_02', 'F06_陈忙忙', 'SH03-07', 'F02-02', 'TR00-01']
KIND_NAME = {'V': '头部模板变式', 'S': '同脚本换画面', 'N': '新测试', 'X': '只换前贴（不计）', 'O': '外部合作'}
# 来源（Reina 11/13：「组」改成来源，唯西两组和外部 agency 放在一张表里）
SRC_NAME = {'A': '唯西 A 组', 'B': '唯西 B 组', 'ZDT': '知定堂', 'YP': '悦普', 'AM': 'AnyMedia'}
AG_DOCS = {'ZDT': ('https://my.feishu.cn/wiki/RBAwwr8CRi8xBYkeqQyclodQnny', 'et1SeP'), 'YP': ('https://my.feishu.cn/wiki/OmjFw42Tpiq8lykD9zzclekTnfd', '5cypAT')}

# 头部模板：表里行号、简称、原片标识（名字里带这些就是照这个模板做的）。链到「头部素材结构提取和变式（11/9）」那一行的代表素材格
TPL_SHEET = 'https://my.feishu.cn/sheets/VEBUs3HTjh3dHqtojlsckJzmnqS?sheet=24e18e'
TEMPLATES = [
    (2, 'LG03 学语言', ['英语口语陪练与个性化带学']), (3, 'PS03 微信转发通知', ['在微信里直接跟Today对话']), (4, 'PS02 恩泽贝拉选课', ['恩泽哥哥和贝拉妹妹']),
    (5, 'WK01 约多人会议', ['W11-ljq-01', '约多人会议：查空档']), (6, 'NT01 说来惭愧', ['NT01-说来惭愧']), (7, 'WK01 会后跟进', ['W01-zl-07', '开完会整理行动项']),
    (8, 'WK05 发票报销 kol', ['整理电子发票和差旅报销_01']), (9, 'HL00 neko 健康', ['H08_neko']), (10, 'IN01 S 赛追战队', ['A18-06']),
    (11, 'PS03 接娃撞车', ['提前协调工作与接娃安排_01']), (12, 'PS01 每天一张卡', ['每天一张卡看清日程和待办_01']), (13, 'LG01 查资料给出处', ['L06-05']),
    (14, 'WK02 97 年大学老师', ['找出工作邮箱里遗漏的重要邮件']), (15, 'LG01 囤书不读', ['个性化读书与自我提升计划_02']), (16, 'LG01 论文 100 篇', ['LG01-03-zl']),
    (17, 'SH04 下班吃什么', ['A05-03']), (18, 'SH01 自动扣费分手梗', ['M01-05']), (19, 'HL02 一日三餐 vlog', ['按训练和做饭时间安排一日三餐_02']),
    (20, 'PS02 陈忙忙双职工', ['F06_陈忙忙']), (21, 'SH03 钱被多扣', ['SH03-07']), (22, 'PS03 门口漏通知', ['F02-02']), (23, 'TR00 回爸妈家不急', ['TR00-01']),
]


def tpl_link(row):
    return TPL_SHEET + '&range=' + base64.b64encode(f'F{row}'.encode()).decode().rstrip('=')


def tpl_of_name(name):
    for row, short, keys in TEMPLATES:
        if any(k in name for k in keys):
            return dict(tn=short, tl=tpl_link(row))
    return {}


ALIAS = {4: ['PS02 恩泽贝拉'], 9: ['HL00 neko'], 20: ['PS02 陈忙忙'], 3: ['PS03 微信转发'], 11: ['PS03 接娃撞车'], 12: ['PS01 每天一张卡'], 15: ['LG01 囤书不读'], 14: ['WK02 97 年大学老师'], 8: ['WK05 发票报销'], 19: ['HL02 一日三餐']}


def tpl_of_label(label):
    for row, short, keys in TEMPLATES:
        if any(a in (label or '') for a in [short] + ALIAS.get(row, [])):
            return dict(tn=short, tl=tpl_link(row))
    return {}

STREAM = 'https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/all/{}/'
UCS = json.load(open(os.path.join(ROOT, 'tools/ucs.json'), encoding='utf-8'))
TPLJ = json.load(open(os.path.join(ROOT, 'tools/templates.json'), encoding='utf-8'))
STOP = re.compile(r'^(扩量|二创|新剪|精剪|精简|AI素材|AI重拍|照真人|同脚本换画面|新角度|换角度|原片|推送视频|修改|合规|KOC非原生|KOL非原生|全文重配|只剪辑|[ABab]组|今天|新拍|重配|today|koc|kol)')
EDITORS = {'叮叮', '小月', '耶耶', '小李', '包子', '叮当'}


def variable(x):
    """头部模板变式这一条换的是什么：先看素材名里写的变量，再看「换角度+NN」对上模板的第几个角度，再看排期行里写的，最后退回原片的场景。"""
    name = x['name']
    for row, short, keys in TEMPLATES:
        k = next((k for k in keys if k in name), None)
        if not k:
            continue
        m = re.search(r'换角度\+?0?(\d+)', name)
        ang = TPLJ.get(str(row), {}).get('angles', [])
        if m and 0 < int(m.group(1)) <= len(ang):
            return ang[int(m.group(1)) - 1].replace('｜', '：')
        tail = name.split(k, 1)[1]
        toks = [t for t in re.split(r'[_\-【】\[\]（）()\s]+', tail) if re.search(r'[一-龥]', t) and not STOP.match(t) and t not in EDITORS and 2 <= len(t) <= 14]
        if toks:
            return '·'.join(toks[:2])
        h = x.get('how', '')
        if re.search(r'换|新场景|新人群', h):
            return h
        if x.get('sc'):
            return x['sc']
        if x.get('uc') and x['uc'] != short[:4]:
            return f"换 use case：{x['uc']} {UCS.get(x['uc'], {}).get('short', '')}（名字和排期没写具体变量）"
        sc = TPLJ.get(str(row), {}).get('scene', '')
        return ('同脚本换画面，原片场景：' if x['k'] == 'S' else '没写变量，原片场景：') + sc
    return x.get('sc', '')


def norm(n):
    n = re.sub(r'\.(mp4|mov|m4v)$', '', n.strip(), flags=re.I)
    n = re.sub(r'^推送视频[_-]?', '', n)
    n = re.sub(r'[-_]?[bB]组$', '', n)
    n = re.sub(r'[_-](改动|合规修改|修改\d*)$|\s*\(\d+\)$', '', n)
    return re.sub(r'[^一-龥a-zA-Z0-9]', '', n).lower()


def cell_link(g, tab, col, row):
    rng = base64.b64encode(f'{col}{row}'.encode()).decode().rstrip('=')
    return f'{DOCS[g]}?sheet={tab}&range={rng}'


def load_tsv(folder, year):
    out = []
    for p in sorted(glob.glob(os.path.join(folder, '*.tsv'))):
        for line in open(p, encoding='utf-8').read().splitlines():
            f = line.split('\t')
            if len(f) < 10 or not f[0] in ('A', 'B'):
                continue
            g, tab, row, col, md, uc, sc, kind, t, name = f[:10]
            how = f[10].strip() if len(f) > 10 else ''
            tok = f[11].strip() if len(f) > 11 else ''
            st = f[12].strip() if len(f) > 12 else ''
            name = name.strip()
            if not re.search(r'[_-]', name) or len(name) < 10:
                continue
            out.append(dict(g=g, tab=tab, row=int(row), col=col, d=f'{year}-{md[:2]}-{md[2:]}', uc=uc.strip(), sc=sc.strip(), k=kind, t=t, name=name, how=how, tok=tok, st=st))
    return out


def classify(x):
    if x['k'] in ('X', 'S', 'V'):
        return x['k']
    if '同脚本换画面' in x['name']:
        return 'S'
    if any(k in x['name'] for k in TEMPLATE_KEYS):
        return 'V'
    return 'N'


KX = {'A': 'kMJdAv', 'B': '3KtioB'}
STAGE_TABS = {'A': 'f18d7b', 'B': 'c665d9'}
STAGE_KX = {'A': 'kMJdAv', 'B': '3KtioB'}


def stage(folder, names, T):
    """还没成片的脚本（Reina 11/11）：tools/script_stage.js 在两组脚本表和扩量排期跑出来的 stage_<tab>.json，只看最新时间点，不追溯过去。
    还在脚本中 = 脚本状态是需修改 / 修改后待审核 / 未审核；脚本已完成、还没开始做 = 可制作、成片空着，而且交付日在本周（以前的不算）。
    说了不要做的、弃用的都不算：脚本备注里写了（script_stage.js 已去掉），或对应的扩量排期行写了先不拍 / 弃用 / 顺延（x）。
    交付日：A 组按脚本名里写的扩量排期行号（「-75-」「76行」「【60】」「_158_」）取那一行的日期，热点按名字里的 MMDD，都没有就沿用表里上一条的；
    B 组按脚本表的产出日期，没有就按扩量排期「45，46脚本已贴表」写到的那一行的日期。
    脚本表里成片没回填、但同 use case 同标题的素材已经交了（扩量表、另一组、分日表里有）的也不算，单列 done。没读到就沿用 notes/output-stage.json 里上次的。"""
    p = os.path.join(ROOT, 'notes/output-stage.json')
    old = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    out = dict(old)
    mon = T - dt.timedelta(days=T.weekday())
    week = {(mon + dt.timedelta(days=i)).strftime('%m%d') for i in range(7)}
    for g, tab in STAGE_TABS.items():
        f = os.path.join(folder, f'stage_{tab}.json')
        if not os.path.exists(f):
            continue
        d = json.load(open(f, encoding='utf-8'))
        if isinstance(d, str):
            d = json.loads(d)
        fk = os.path.join(folder, f'stage_{STAGE_KX[g]}.json')
        kx = json.load(open(fk, encoding='utf-8')).get('rows', {}) if os.path.exists(fk) else {}
        sc2kx = {}
        for r, y in kx.items():
            for n in y.get('sc', []):
                sc2kx.setdefault(n, y)

        def plan_of(x):
            if g == 'B':
                return sc2kx.get(x['r'])
            m = re.findall(r'(?:[-_【]|^)(\d{2,3})(?=[-_】]|行)', x['name'])
            m = [n for n in m if 20 <= int(n) <= 999]
            return kx.get(m[-1]) if m else None

        allx = sorted([dict(x, ready=False) for x in d.get('in_script', [])] + [dict(x, ready=True) for x in d.get('ready', [])], key=lambda x: x['r'])
        last = ''
        ins, ready, done, killed, old_n = [], [], [], d.get('killed', 0), 0
        for x in allx:
            y = plan_of(x)
            day = x.get('d') or (y or {}).get('d') or ''
            if not day:
                m = re.search(r'(?<!\d)(1[012][0-3]\d)(?!\d)', x['name'])
                day = m.group(1) if m and g == 'A' else ''
            if day:
                last = day
            else:
                day = last
            x['link'] = cell_link(g, tab, 'A', x['r'])
            if day and day != 'next':
                x['d'] = day
            if y and y.get('x'):
                killed += 1
                continue
            if not x.pop('ready'):
                ins.append(x)
                continue
            if day not in week:
                old_n += 1
                continue
            m = re.search(r'[A-Z]{2}\d{2}[-_](?:\d{2}[-_])?([一-龥A-Za-z0-9]{4,14})', x['name'])
            tok = m.group(1) if m else ''
            hit = next((n for n in names if tok and x.get('uc') and tok in n and x['uc'] in n and not any(tok in k for k in TEMPLATE_KEYS)), '') if not re.fullmatch(r'AI素材.*|新角度.*|\d+', tok or '0') else ''
            if hit:
                done.append(dict(x, by=hit))
            else:
                ready.append(x)
        out[g] = dict(asof=T.isoformat(), week=mon.isoformat(), start=d.get('start'), tab=tab, in_script=ins, ready=ready, done=done, killed=killed, old=old_n)
    json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return out


def batches(plan, items, w0, T):
    """生产批次：排期表里的一行是一个批次（排了几条、哪天交），把这行交上来的成片挂上去；脚本表、二剪表里没在扩量排期登记的成片按表和行单独成批。"""
    w1 = w0 + dt.timedelta(days=6)
    out = {}
    for e in plan.get('E', []):
        d = dt.date.fromisoformat(e['d'])
        if not (w0 <= d <= w1) or e.get('s') == 'cut':
            continue
        m = re.search(r'([AB]) 组(?:扩量)?第 ?(\d+)', e.get('src', ''))
        if not m:
            continue
        g, row = m.group(1), int(m.group(2))
        key = f'{g}|{KX[g]}|{row}'
        b = out.setdefault(key, dict(g=g, tab=KX[g], row=row, d=e['d'], uc=e['uc'], sc=e.get('sc', ''), k=e.get('k', ''), t=e.get('t', ''), n=0,
                                     how=e.get('how', ''), tpl=e.get('tpl', ''), src=e.get('src', '').split('：', 1)[-1], link=cell_link(g, KX[g], 'K', row), items=[]))
        b['n'] += e['n']
        if not b.get('tn'):
            b.update(tpl_of_label((e.get('tpl') or '') + ' ' + e.get('src', '')))
    def day(s):
        return dt.date.fromisoformat(s)
    rest = []
    for x in items:  # 先按扩量表行号对上
        key = f"{x['g']}|{x['tab']}|{x['row']}"
        if key in out and out[key]['n'] is not None:
            out[key]['items'].append(dict(name=x['name'], link=x.get('link', ''), k=x.get('k', '')))
            x['_b'] = key
        else:
            rest.append(x)
    for x in rest:  # 脚本表、二剪表交上来的：按组、use case、AI/二创、是不是变式对上排期行（交付日在排期日当天到后两天），没交满的优先
        isv = x.get('k') in ('V', 'S')
        c = [b for b in out.values() if b['n'] is not None and b['g'] == x['g'] and b['uc'] and b['uc'] == x.get('uc')
             and 0 <= (day(x['d']) - day(b['d'])).days <= 2  # 交付日在排期日当天或之后两天内，不往后面的排期上挂
             and (b.get('k') in ('变式', '同脚本换画面')) == isv and (b.get('t') == ('AI' if x['t'] == 'A' else '二创'))]
        c.sort(key=lambda b: (len(b['items']) >= b['n'], abs((day(b['d']) - day(x['d'])).days), b['d']))
        if c:
            c[0]['items'].append(dict(name=x['name'], link=x.get('link', ''), k=x.get('k', '')))
            c[0]['by_uc'] = True
            continue
        key = f"{x['g']}|{x['tab']}|{x['row']}"
        if key not in out:
            out[key] = dict(g=x['g'], tab=x['tab'], row=x['row'], d=x['d'], uc=x.get('uc', ''), sc=x.get('sc', ''), k='', t='AI' if x['t'] == 'A' else '二创', n=None,
                            how='', tpl='', src='排期外：' + TABS.get(x['tab'], x['tab']), link=cell_link(x['g'], x['tab'], 'A', x['row']), items=[])
        out[key]['items'].append(dict(name=x['name'], link=x.get('link', ''), k=x.get('k', '')))
    for b in out.values():
        got = len(b['items'])
        b['got'] = got
        b['st'] = '排期外' if b['n'] is None else ('交齐' if got >= b['n'] else ('还没到' if b['d'] > T.isoformat() else ('今天交' if b['d'] == T.isoformat() else (f"差 {b['n'] - got}" if got else '没交'))))
    return sorted(out.values(), key=lambda b: (b['d'], b['g'], b['row']), reverse=True)


def ag_day(s, T):
    """11月9日、11/11/2026、11.13、2026-11-12 都认；年份缺了按 T 补。"""
    s = (s or '').strip()
    m = re.match(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r'(\d{1,2})[/.月](\d{1,2})(?:[/.](\d{4}))?', s)
        if not m:
            return None
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3) or T.year)
    try:
        return dt.date(y, mo, d)
    except ValueError:
        return None


def ag_uc(s):
    m = re.search(r'[A-Za-z]{2}\d{2}', s or '')
    return m.group(0).upper() if m else ''


def agency(folder, kv, T):
    """外部 agency 的成片（Reina 11/13）：知定堂星广（排期和审核 et1SeP，成片审核「通过」，一行按视频链接里的视频数算条数，日期取交付日期，晚于今天的算今天）、
    悦普抖音星图（执行表 5cypAT，只算抖音、合作形式星图，已发布或有发布链接，日期取发布档期）、AnyMedia（「国区投放素材」Today KOL/KOC 视频 tab，代理商写 AnyMedia、平台是抖音、有视频链接的，日期取发布日期；小红书不放）。
    结果存 notes/output-agency.json；哪家这次没读到就沿用上次的。"""
    p = os.path.join(ROOT, 'notes/output-agency.json')
    store = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}
    def put(src, items):
        store[src] = dict(asof=T.isoformat(), items=items)
    f = os.path.join(folder or '', 'et1SeP.json')
    if folder and os.path.exists(f):
        rows = json.load(open(f, encoding='utf-8'))['rows']
        doc, tab = AG_DOCS['ZDT']
        out = []
        for x in rows:
            if '通过' not in (x.get('vst') or ''):
                continue
            d = ag_day(x.get('d'), T)
            if not d:
                continue
            d = min(d, T)
            n = max(1, int(x.get('vid') or 0))
            for i in range(n):
                out.append(dict(g='ZDT', typ='星广', d=d.isoformat(), uc=ag_uc(x.get('uc')), name=f"知定堂_星广_{x.get('acct') or '账号未填'}_{x.get('uc') or ''}_第{x['r']}行" + (f'_{i + 1}' if n > 1 else ''),
                                link=f"{doc}?sheet={tab}&range=" + base64.b64encode(f"I{x['r']}".encode()).decode().rstrip('=')))
        put('ZDT', out)
    f = os.path.join(folder or '', '5cypAT.json')
    if folder and os.path.exists(f):
        rows = json.load(open(f, encoding='utf-8'))['rows']
        doc, tab = AG_DOCS['YP']
        out = []
        for x in rows:
            if not (x.get('pub') or '已发布' in (x.get('st') or '')):
                continue
            d = ag_day(x.get('d'), T)
            if not d:
                continue
            out.append(dict(g='YP', typ='抖音星图', d=min(d, T).isoformat(), uc=ag_uc(x.get('uc')), name=f"悦普_抖音星图_{x.get('name')}",
                            link=f"{doc}?sheet={tab}&range=" + base64.b64encode(f"A{x['r']}".encode()).decode().rstrip('=')))
        put('YP', out)
    if kv and os.path.exists(kv):
        v = json.load(open(kv, encoding='utf-8'))['values']
        H = v[0]
        ix = {h: H.index(h) for h in ('平台', '达人类别', '发布日期', '博主名称', '代理商', '视频链接', 'UC_ID') if h in H}
        g = lambda r, h: (r[ix[h]] if h in ix and ix[h] < len(r) else '').strip()
        out = []
        for r in v[1:]:
            if g(r, '代理商').lower().replace(' ', '') != 'anymedia' or not g(r, '视频链接') or g(r, '平台') != '抖音':  # 小红书达人不放（Reina 11/13）
                continue
            d = ag_day(g(r, '发布日期'), T)
            if not d:
                continue
            out.append(dict(g='AM', typ=f"{g(r, '平台')}达人", d=d.isoformat(), uc=ag_uc(g(r, 'UC_ID')), name=f"AnyMedia_{g(r, '平台')}{g(r, '达人类别')}_{g(r, '博主名称')}", link=g(r, '视频链接')))
        put('AM', out)
    json.dump(store, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    items = []
    for src, y in store.items():
        for x in y['items']:
            items.append(dict(x, k='O', t='O', ok=True, lk='v' if x['g'] == 'AM' else 'f'))
    return items, {src: y['asof'] for src, y in store.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--sheet')
    ap.add_argument('--agency', help='tools/agency_read.js 读出来的 5cypAT.json、et1SeP.json 所在目录')
    ap.add_argument('--kv', help='「国区投放素材」Today KOL/KOC 视频 tab 的 values JSON（AnyMedia）')
    a = ap.parse_args()
    T = dt.date.fromisoformat(a.date)
    ucs = json.load(open(os.path.join(ROOT, 'tools/ucs.json'), encoding='utf-8'))
    scenes = json.load(open(os.path.join(ROOT, 'tools/scenes.json'), encoding='utf-8'))
    smap = json.load(open(os.path.join(ROOT, 'notes/scene-map.json'), encoding='utf-8'))
    links = json.load(open(os.path.join(ROOT, 'tools/links.json'), encoding='utf-8'))
    store_p = os.path.join(ROOT, 'notes/output-items.json')
    store = json.load(open(store_p, encoding='utf-8')) if os.path.exists(store_p) else {}

    # 分日表：素材名 -> 素材 ID、累计消耗、首花
    by_name, sheet_names = {}, set()
    if a.sheet:
        v = json.load(open(a.sheet, encoding='utf-8'))['values']
        H = v[0]
        iD, iI, iN, iC = H.index('日期'), H.index('素材ID'), H.index('素材名'), H.index('消耗')
        sheet_names = set(r[iN] for r in v[1:] if len(r) > iN)
        for r in v[1:]:
            if len(r) <= iC:
                continue
            k = norm(r[iN])
            c = float(re.sub(r'[^\d.]', '', r[iC]) or 0)
            x = by_name.setdefault(k, dict(id=r[iI], cost=0.0, first=''))
            x['cost'] += c
            if c > 0 and (not x['first'] or r[iD] < x['first']):
                x['first'] = r[iD]

    new = load_tsv(a.dir, T.year)
    seen = {}
    for x in sorted(new, key=lambda x: TAB_RANK.get(x['tab'], 9)):
        key = x['g'] + '|' + norm(x['name'])
        if key in seen:  # 同一条素材在扩量表和脚本表都登记了：留扩量表那条，脚本表的链接放 alt
            seen[key].setdefault('alt', []).append(cell_link(x['g'], x['tab'], x['col'], x['row']))
            p = seen[key]
            if x.get('st') and ('通过' == x['st'] or not p.get('st')):  # B 组扩量表没有「成片状态」列，审核结果在脚本表/二剪表那条上
                p['st'] = x['st']
            if not p.get('tok') and x.get('tok'):  # 成片附件在脚本表那一格：链到那一格
                p['tok'] = x['tok']
                p['cell'] = cell_link(x['g'], x['tab'], x['col'], x['row'])
            continue
        x['cell'] = cell_link(x['g'], x['tab'], x['col'], x['row'])
        x['where'] = f"{TABS.get(x['tab'], x['tab'])}第 {x['row']} 行"
        seen[key] = x
    for key, x in seen.items():
        old = store.get(key, {})
        x['k'] = classify(x)
        x.update(tpl_of_name(x['name']) if x['k'] in ('V', 'S') else {})
        if x['k'] in ('V', 'S'):
            x['var'] = variable(x)
        store[key] = {**old, **x}

    # 补维度和投放数据
    for key, x in store.items():
        u = ucs.get(x.get('uc') or '', {})
        x['l1'] = u.get('l1', '')
        x['ucn'] = u.get('short', '')
        b = by_name.get(norm(x['name']))
        if b:
            x['mid'] = b['id']
            x['cost'] = round(b['cost'])
            x['first'] = b['first']
            v = links.get(b['id'], {}).get('video')
            if v:
                x['video'] = v
            s = smap.get(b['id'])
            if not x.get('sc') and s and s.get('uc') in scenes:
                t = next((y['t'] for y in scenes[s['uc']]['scenes'] if y['n'] == s.get('s')), '')
                if t:
                    x['sc'] = t
    for x in store.values():  # 投出去的直接链巨量/唯西日报的永久视频；没投的链飞书表里成片那一格（附件直链飞书会做 Referer 校验，从看板点开报「Referer check fail」，11/10 试过）
        x['ok'] = x.get('st') == '通过'  # 只有「成片状态」写了通过的才算数、才放链接；需修改/修改后待审核/待审核/没填的都不算（Reina 11/10）
        x['link'] = (x.get('video') or x.get('cell') or '') if x['ok'] else ''
        x['lk'] = 'v' if x.get('video') else 'f'
    json.dump(store, open(store_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    for x in store.values():
        x['typ'] = 'AI' if x.get('t') == 'A' else '二创'
    ag, ag_asof = agency(a.agency, a.kv, T)
    for x in ag:
        u = ucs.get(x.get('uc') or '', {})
        x['l1'], x['ucn'] = u.get('l1', ''), u.get('short', '')
    names = set(x['name'] for x in store.values()) | sheet_names
    stg = stage(a.dir, names, T)
    mon = T - dt.timedelta(days=T.weekday())
    weeks = sorted({(dt.date.fromisoformat(x['d']) - dt.timedelta(days=dt.date.fromisoformat(x['d']).weekday())).isoformat() for x in list(store.values()) + ag}, reverse=True)
    agt = json.load(open(os.path.join(ROOT, 'tools/agency_targets.json'), encoding='utf-8'))
    tpl = open(os.path.join(ROOT, 'tools/output_template.html'), encoding='utf-8').read()
    plan = json.load(open(os.path.join(ROOT, 'tools/schedule_plan.json'), encoding='utf-8'))
    for wk in weeks:
        if wk < (mon - dt.timedelta(days=7)).isoformat():
            continue  # 只重算这周和上周
        w0 = dt.date.fromisoformat(wk)
        wk_all = sorted([x for x in store.values() if w0.isoformat() <= x['d'] <= (w0 + dt.timedelta(days=6)).isoformat()], key=lambda x: (x['d'], x['g'], x['k'], x['uc']))
        items = [x for x in wk_all if x.get('ok')] + sorted([x for x in ag if w0.isoformat() <= x['d'] <= (w0 + dt.timedelta(days=6)).isoformat()], key=lambda x: (x['d'], x['g']))
        tg = {}
        for key, src in (('zdt', 'ZDT'), ('yp', 'YP')):
            past = sorted(k for k in agt if re.match(r'\d{4}-\d{2}-\d{2}$', k) and k <= wk and key in agt[k])
            if past:
                tg[src] = dict(t=agt[past[-1]][key]['t'], stale=past[-1] != wk)
        pend = [dict(g=x['g'], d=x['d'], k=x['k'], t=x['t'], typ=x.get('typ', ''), uc=x.get('uc', ''), ucn=x.get('ucn', ''), name=x['name'], st=x.get('st') or '还没审') for x in wk_all if not x.get('ok')]
        data = dict(week=wk, T=T.isoformat(), days=[(w0 + dt.timedelta(days=i)).isoformat() for i in range(7)], items=items, pend=pend, kinds=KIND_NAME, weeks=weeks,
                    batches=batches(plan, [x for x in items if x['g'] in ('A', 'B')], w0, T), ucn={k: v.get('short', '') for k, v in ucs.items()}, target=plan.get('week_total', {'A': 150, 'B': 150}),
                    stage=stg if w0 == mon else None, src=SRC_NAME, agt=tg, ag_asof=ag_asof)
        html = tpl.replace('{{DATA}}', json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
        for path in [os.path.join(ROOT, 'output', wk, 'index.html')] + ([os.path.join(ROOT, 'output', 'index.html')] if w0 == mon else []):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            rel = '../../' if path.endswith(os.path.join(wk, 'index.html')) else '../'
            open(path, 'w', encoding='utf-8').write(html.replace('{{REL}}', rel))
    json.dump([dict(week=w) for w in weeks], open(os.path.join(ROOT, 'outputs.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    cnt = {g: {k: sum(1 for x in store.values() if x['g'] == g and x['k'] == k and x.get('ok') and x['d'] >= mon.isoformat()) for k in 'VSNX'} for g in 'AB'}
    sg = {g: dict(in_script=len(stg[g]['in_script']), ready=len(stg[g]['ready']), done=len(stg[g]['done']), killed=stg[g].get('killed'), old=stg[g].get('old'), asof=stg[g]['asof']) for g in 'AB' if g in stg}
    print(json.dumps(dict(items=len(new), kept=len(seen), store=len(store), week=mon.isoformat(), count=cnt, stage=sg), ensure_ascii=False))


if __name__ == '__main__':
    main()
