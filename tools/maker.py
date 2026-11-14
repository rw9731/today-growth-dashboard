"""素材制作方（Reina 11/14）：唯西 A 组、唯西 B 组、唯西星广、唯西自建号、知定堂星广、客供。
判断顺序：星广任务清单（notes/star.json，任务 ID 定是哪家）> 来源=客供 > 名字里写了 A组/B组 > 名字里最后一个剪辑师代号。
剪辑师代号是 11/14 从唯西 A 组「脚本及成片」、B 组「脚本&成片」「真人素材和ai切片二剪」读出来的：A 组用拼音缩写，B 组用中文昵称。
"""
import re

STAR_TASK = {'7702316618969333810': '唯西星广', '7706501371755200522': '知定堂星广', '7706732258950479882': '知定堂星广'}
A_ED = {'zxc', 'sjl', 'cw', 'xyn', 'zl', 'wq', 'lst', 'ltq', 'hxq', 'hyq', 'yyz', 'zx', 'wzy', 'fjh', 'ljq', 'sj', 'cxx'}
B_ED = {'小李', '耶耶', '小月', '包子', '叮叮', '白白'}
_tok = re.compile(r'(?<![A-Za-z])(?:精剪|精简)?\d?([a-z]{2,3})\d{0,2}(?![A-Za-z])|(小李|耶耶|小月|包子|叮叮|白白)')


def maker(name, src='', star=None, zjh=False):
    """star: notes/star.json 里这条的 [标题, 昵称, 任务ID]；zjh: 在唯西自建号表里对上过。"""
    if star:
        if zjh:
            return '唯西自建号'
        return STAR_TASK.get(str(star[2]) if len(star) > 2 else '', '星广')
    if src == '客供':
        return '客供'
    n = name or ''
    if re.search(r'[aA]组', n):
        return '唯西A组'
    if re.search(r'[bB]组|_b-\d', n):
        return '唯西B组'
    if '新角度扩量' in n:  # A 组「脚本及成片」的命名
        return '唯西A组'
    last = ''
    for m in _tok.finditer(n):
        t = m.group(1) or m.group(2)
        if t in A_ED or t in B_ED:
            last = t
    if last in A_ED:
        return '唯西A组'
    if last in B_ED:
        return '唯西B组'
    # 10 月分 A、B 组以前唯西的命名（learning_、work_、home&family_ 开头，today koc / kol 二剪），分不出组
    if re.match(r'^(learning|work|home&family|health|money|ai个人助手|life)_', n, re.I) or re.search(r'today ko[cl]_', n):
        return '唯西'
    return ''
