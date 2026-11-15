"""排期表 UC 自查（Reina 11/15：排期表上的 use case 不能分错）。读 /tmp/h/aud_<tab>.json（tools/plan_audit_read.js 读的），列出要人看的行：
- UC 不在库，或是已合并、下线的旧编号（tools/uc_codes.json 里的键，比如 WK06、A07）；
- LG02（只放学生）的行里出现在职、转行、考证这类词；LG04 的行里只有学生的词；LG03（没考试）的行里有考试；
- 记账、信用卡、回款写在 SH01（应是 FN02）。
plan_fix.json 里已经改过的行不再报。输出空列表才算过；有就逐行看内容，改好写进 notes/plan_fix.json 并改飞书表，再跑 plan_build.py。
用法：python3 tools/plan_check.py [/tmp/h]
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
D = sys.argv[1] if len(sys.argv) > 1 else '/tmp/h'
ucs = json.load(open(os.path.join(HERE, 'ucs.json'), encoding='utf-8'))
codes = {k for k in json.load(open(os.path.join(HERE, 'uc_codes.json'), encoding='utf-8')) if not k.startswith('_')}
fix = json.load(open(os.path.join(ROOT, 'notes', 'plan_fix.json'), encoding='utf-8'))
work = re.compile(r'在职|职场|上班|下班|CPA|注会|法考|中级|初级会计|教资|转行|考证|宝妈|妈妈|会计|PMP|一建|二建|在职考研')
stud = re.compile(r'大学生|学生|期末|四六级|作业|课表|留学|室友|宿舍|高考|中考|绩点|选课')
exam = re.compile(r'考试|备考|考证|法考|行测|考公|四六级|期末|考研|CPA|教资')
money = re.compile(r'记账|信用卡|还款|回款|钱花在哪|余额')
out = []
for t in ['kMJdAv', 'f18d7b', 'nPw5Dc', 'c665d9', 'EnYgPG', '3KtioB']:
    p = f'{D}/aud_{t}.json'
    if not os.path.exists(p):
        out.append([t, 0, '', '没读到这个 tab']); continue
    a = json.load(open(p, encoding='utf-8'))
    for r, uc, vals in a['rows']:
        f = fix.get(t, {}).get(str(r))
        if f:
            uc = f[0]
        if not uc or uc == '自选':
            continue
        txt = re.sub(r'把转行、考证这类大目标[^-]*', '', ' '.join(vals))  # 旧 LG02 脚本名里带「转行、考证」，不算内容
        why = []
        if uc not in ucs or uc in codes:
            why.append('UC 不在库或已合并/下线')
        if uc == 'LG02' and work.search(txt) and not re.search(r'学生线', txt):
            why.append('LG02 但有在职/转行的词')
        if uc == 'LG04' and stud.search(txt) and not work.search(txt):
            why.append('LG04 但只有学生的词')
        if uc == 'LG03' and exam.search(txt):
            why.append('LG03 但有考试')
        if uc == 'SH01' and money.search(txt) and not re.search(r'扣费|会员|续费|订阅', txt):
            why.append('SH01 但讲的是记账/还款（FN02）')
        if why and not (f and f[0] == uc and len(f) > 1):
            out.append([t, r, uc, '；'.join(why), txt[:120]])
print(json.dumps(out, ensure_ascii=False, indent=0))
