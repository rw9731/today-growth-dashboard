// 唯西排期表、成片表按列读（Reina 11/15）：和 tools/plan_uc_read.js 读同样 6 个 tab，但每行按列分开返回，tools/plan_build.py 用它认出「原素材（照着改）」列（参照的原片不算这一行出的片），检查 UC 有没有分错也看它。
// 每个 tab navigate 到带 ?sheet= 的网址后跑全文，返回值存成文件，用 /tmp/h/fromfile.py 解析成 /tmp/h/aud_<tab>.json。只读。
await new Promise(r=>setTimeout(r,7000));
let sh=null; for(let i=0;i<40;i++){ try{ sh=window.spread&&window.spread.getActiveSheet(); if(sh&&sh.getRowCount()>3) break; }catch(e){} await new Promise(r=>setTimeout(r,500)); }
const R=sh.getRowCount(), C=Math.min(sh.getColumnCount(),40);
let hr=-1, uc=-1; for(let r=0;r<6&&uc<0;r++) for(let c=0;c<C;c++){ const t=(sh.getText(r,c)||'').replace(/\s/g,''); if(t==='UC_ID'||t==='UC'||t.startsWith('UC_ID')){ uc=c; hr=r; break; } }
const H=[...Array(C)].map((_,c)=>(sh.getText(hr,c)||'').replace(/\s/g,''));
const keep=H.map((h,c)=>c!==uc&&/日期|一级|Use|细分|原素材|视频|怎么改|命名|脚本|扩量素材名|成片|条数/i.test(h)&&!/备注|状态|审/.test(h)?c:-1).filter(c=>c>=0);
const cell=(r,c)=>{ let segs=[]; try{ segs=(sh.getSegmentArray(r,c)||[]).map(s=>s.text||''); }catch(e){} const t=sh.getText(r,c)||''; const extra=segs.join(' ').trim(); return (extra&&!t.includes(extra)?t+' '+extra:t).replace(/\s+/g,' ').trim(); };
const out=[]; for(let r=hr+1;r<R;r++){ const u=(sh.getText(r,uc)||'').trim(); const vals=keep.map(c=>cell(r,c)); if(!u&&!vals.some(v=>v)) continue; out.push([r+1,u,vals]); }
JSON.stringify({AUD:1,tab:location.search,sheet:sh.name(),uc_col:H[uc],hr,cols:keep.map(c=>[c,H[c].slice(0,20)]),rows:out,pad:'x'.repeat(60000)});
