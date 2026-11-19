"""把 oplog.js 的 __opGet 分段结果合并进 notes/jjlog.json（见 tools/oplog_js.py 文件头）。

用法：python3 tools/oplog_save.py --date D /tmp/oplog
读 /tmp/oplog/ids.json 和 op_0.txt、op_1.txt……，每条素材 8 个字符（iOS 新、iOS 老、安卓新、安卓老，各 2 位 36 进制）。
notes/jjlog.json：{"updated": D, "mats": {素材ID: [iOS 新, iOS 老, 安卓新, 安卓老, 拉取日]}}。
同一条素材以最新一次拉取为准（拉取起始日不晚于它的上传日，窗口是完整的）。
"""
import argparse, glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('dir')
    a = ap.parse_args()
    meta = json.load(open(os.path.join(a.dir, 'ids.json')))
    if meta['date'] != a.date:
        raise SystemExit(f"日期对不上：ids.json 是 {meta['date']}")
    ids = meta['ids']
    parts = sorted(glob.glob(os.path.join(a.dir, 'op_*.txt')), key=lambda p: int(re.findall(r'op_(\d+)', p)[0]))
    s = ''.join(open(p).read().strip().strip('"') for p in parts)
    if len(s) != 8 * len(ids):
        raise SystemExit(f'长度对不上：{len(s)} 个字符，应为 {8 * len(ids)}（{len(ids)} 条素材），缺段或多段')
    path = os.path.join(os.path.dirname(HERE), 'notes', 'jjlog.json')
    db = json.load(open(path)) if os.path.exists(path) else {'mats': {}}
    for i, m in enumerate(ids):
        c = [int(s[i * 8 + k * 2:i * 8 + k * 2 + 2], 36) for k in range(4)]
        db['mats'][m] = c + [a.date]
    db['updated'] = max(db.get('updated', ''), a.date)
    db['source'] = '巨量操作日志 opt_log/dataSearch：项目「新建」「新增 视频 添加 素材ID」，窗口 = 上传日到 +2 天'
    json.dump(db, open(path, 'w'), ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'saved': len(ids), 'total': len(db['mats']), 'updated': db['updated']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
