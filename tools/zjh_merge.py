"""把 tools/zjh_read.js 读到的星广任务视频里，自建号抖音号的那些并进 tools/zijianhao.json（只加不删）。
用法：python3 tools/zjh_merge.py /tmp/zjh.json
"""
import datetime as dt, json, os, sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zijianhao.json')


def main():
    got = json.load(open(sys.argv[1]))
    if isinstance(got, str):
        got = json.loads(got)
    z = json.load(open(P))
    acc = z['accounts']
    added, seen = [], 0
    for i, v in (got.get('videos') or {}).items():
        if v.get('dyid') in acc:
            seen += 1
            if i not in z['ids']:
                z['ids'][i] = {'acc': acc[v['dyid']], 'name': v.get('name', '')}
                added.append(i)
    others = sorted({(v.get('acc'), v.get('dyid')) for v in (got.get('videos') or {}).values() if v.get('dyid') and v.get('dyid') not in acc})
    z['updated'] = dt.date.today().isoformat()
    json.dump(z, open(P, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'task_total': got.get('total'), 'read': got.get('n'), 'zjh_in_task': seen, 'added': added,
                      'zjh_ids': len(z['ids']), 'other_accounts': others}, ensure_ascii=False))
    if got.get('total') and got.get('n') != got.get('total'):
        print('WARNING 星广任务没读全', got.get('n'), '/', got.get('total'))


if __name__ == '__main__':
    main()
