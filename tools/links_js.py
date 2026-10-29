"""Make the browser snippets that find links for materials still missing one.

Usage:
  python3 tools/links_js.py /tmp/results.json --out /tmp/linkjs

Writes up to three files, each a JavaScript snippet to run with the built-in browser
(javascript_tool) on the page named in its first comment line:
  yuanpian.js  -> 唯西表「today ai koc kol 真人原素材」 (?sheet=6AHEfW): KOC/KOL 原片 = 博主原帖
  chengpian.js -> 唯西表「脚本及成片」 (?sheet=f18d7b): AI 短剧 成片 = 表格里那一格
  yulan.js     -> 唯西「Today-日报」「每日素材数据」 (?sheet=jPPl6w): 巨量里投的那条视频（每条素材都要，扩量的原素材也要）
Each snippet returns a JSON object {素材ID: 链接}. Save each result as <name>.json next to
the snippet, then run tools/links_merge.py.
Prints how many materials need a link; 0 means nothing to do.
"""
import argparse, json, os

PAGES = {
    'yuanpian': 'https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc?sheet=6AHEfW',
    'chengpian': 'https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc?sheet=f18d7b',
    'yulan': 'https://www.feishu.cn/wiki/MF08weqhAivx3SkRkeTck5R3nkc?sheet=jPPl6w',
}

WAIT = """let sh=null; for (let i=0;i<50;i++){ try { sh = window.spread && window.spread.getActiveSheet(); if (sh && sh.name().includes(%s) && sh.getText(1,%d)) break; } catch(e){} await new Promise(r=>setTimeout(r,500)); }
if (!sh || !sh.name().includes(%s)) throw new Error('sheet not loaded');
"""

YUANPIAN = """const NEED = %s;
const ys=[]; for (let r=1;r<sh.getRowCount();r++){ const n=(sh.getText(r,3)||'').trim(); if(!n || !n.includes('_today ')) continue; let link=''; try { const u=(sh.getSegmentArray(r,6)||[]).find(s=>s.link||s.type==='url'); link=u?(u.link||u.text):''; } catch(e){} if(!link) link=((sh.getText(r,6)||'').match(/https?:\\/\\/\\S+/)||[''])[0]; ys.push([n,link]); }
const clean=s=>s.replace(/^推送视频_/,'').replace('todaykoc','today koc').replace('todaykol','today kol').trim();
const out={}; for (const [id,name] of NEED){ const n=clean(name); let best=null; for (const [k,link] of ys){ if (n===k || (n.startsWith(k) && /[_\\-]/.test(n[k.length]))) { if (!best || k.length>best[0].length) best=[k,link]; } } if (best && /^https?:/.test(best[1])) out[id]=best[1]; }
JSON.stringify(out)"""

CHENGPIAN = """const NEED = %s;
const cp=[]; for (let r=1;r<sh.getRowCount();r++){ const d=sh.getText(r,3)||''; let h=''; try { h=(sh.getSegmentArray(r,7)||[]).filter(s=>s.type==='attachment').map(s=>s.text).join(' || '); } catch(e){} if(!h) h=sh.getText(r,7)||''; if (h) cp.push([r+1,d,h]); }
const norm=s=>s.replace(/\\.mp4$/i,'').replace(/\\s*\\(\\d+\\)$/,'').replace(/[_-]合规修改$/,'').trim();
const tok=s=>{ const a=s.match(/[A-Z]{1,2}\\d{2}-\\d{2}-[a-z]+/); if(a) return a[0]; const b=s.match(/[A-Z]\\d{2}-[a-z]+-\\d{2}/); return b?b[0]:''; };
const base='https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc?sheet=f18d7b&range=';
const out={}; for (const [id,name] of NEED){ const n=norm(name), t=tok(name); let hit=cp.find(([r,d,h])=>norm(d)===n || h.split(' || ').some(x=>norm(x)===n)); if(!hit && t){ const c=cp.filter(([r,d,h])=>d.includes(t)||h.includes(t)); const date=(name.match(/20\\d{6}/)||[''])[0]; hit=c.find(x=>date && (x[1]+x[2]).includes(date)) || c.find(x=>(x[1]+x[2]).includes('修改版')===name.includes('修改版')) || c[0]; } if (hit) out[id]=base+btoa('H'+hit[0]).replace(/=+$/,''); }
JSON.stringify(out)"""

YULAN = """const NEED = new Set(%s);
const out={}; for (let r=sh.getRowCount()-1;r>=1;r--){ const id=(sh.getText(r,4)||'').trim(); if(!NEED.has(id) || out[id]) continue; let link=''; try { const u=(sh.getSegmentArray(r,5)||[]).find(s=>s.link||s.type==='url'); link=u?(u.link||u.text):''; } catch(e){} if(!link) link=sh.getText(r,5)||''; if (/^https?:/.test(link)) out[id]=link; }
JSON.stringify(out)"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    res = json.load(open(a.results))
    mats = {m['id']: m for m in res['mat']}
    need = [m for m in mats.values() if m.get('link_type') not in ('原片', '成片')]
    os.makedirs(a.out, exist_ok=True)
    koc = [[m['id'], m['name']] for m in need if 'today koc' in m['name'] or 'today kol' in m['name'] or 'todaykoc' in m['name']]
    aigc = [[m['id'], m['name']] for m in need if [m['id'], m['name']] not in koc]
    files = {}
    if koc:
        files['yuanpian'] = WAIT % ("'真人原素材'", 3, "'真人原素材'") + YUANPIAN % json.dumps(koc, ensure_ascii=False)
    if aigc:
        files['chengpian'] = WAIT % ("'脚本及成片'", 1, "'脚本及成片'") + CHENGPIAN % json.dumps(aigc, ensure_ascii=False)
    links = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'links.json')))
    nolink = [m['id'] for m in mats.values() if not m.get('video')]
    # 扩量分析要对照原素材，原素材不一定在看板里，也一起找视频
    nolink += sorted({i for k in res.get('kl', []) for i in k.get('src_ids', []) if i not in mats and not links.get(i, {}).get('video')})
    if nolink:
        files['yulan'] = WAIT % ("'每日素材数据'", 0, "'每日素材数据'") + YULAN % json.dumps(nolink)
    for k, js in files.items():
        open(os.path.join(a.out, k + '.js'), 'w').write(f'// 在这个页面跑：{PAGES[k]}\n' + js)
    print(json.dumps({'need': len(need), 'koc': len(koc), 'aigc': len(aigc), 'no_video': len(nolink),
                      'snippets': {k: PAGES[k] for k in files}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
