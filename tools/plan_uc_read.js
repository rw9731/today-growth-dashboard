// 唯西排期表、成片表的 UC（Reina 11/15）：在下面 6 个 tab 各跑一次全文（navigate 到带 ?sheet= 的网址再跑），返回值太长会被存成文件（结尾 pad 就是为了让它存文件、不占对话），解析 rows 合并成 notes/plan_uc.json 的 map（键用 tools/uc_resolve.py 的 norm_name）。
// A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：kMJdAv、f18d7b、nPw5Dc；B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：c665d9、EnYgPG、3KtioB。只读。
await new Promise(r=>setTimeout(r,7000));
let sh=null; for(let i=0;i<40;i++){ try{ sh=window.spread&&window.spread.getActiveSheet(); if(sh&&sh.getRowCount()>3) break; }catch(e){} await new Promise(r=>setTimeout(r,500)); }
const R=sh.getRowCount(), C=Math.min(sh.getColumnCount(),40);
let hr=-1, uc=-1; for(let r=0;r<6&&uc<0;r++) for(let c=0;c<C;c++){ const t=(sh.getText(r,c)||'').replace(/\s/g,''); if(t==='UC_ID'||t==='UC'||t.startsWith('UC_ID')){ uc=c; hr=r; break; } }
const H=[...Array(C)].map((_,c)=>(sh.getText(hr,c)||'').replace(/\s/g,''));
const nc=H.map((h,c)=>/命名|素材名|成片|扩量素材名|原素材/.test(h)&&!/备注|状态/.test(h)?c:-1).filter(c=>c>=0);
const out=[]; for(let r=hr+1;r<R;r++){ const u=(sh.getText(r,uc)||'').trim(); if(!u) continue; const names=[]; for(const c of nc){ let segs=[]; try{ segs=(sh.getSegmentArray(r,c)||[]).map(s=>s.text||''); }catch(e){} const t=(sh.getText(r,c)||'')+'\n'+segs.join('\n'); for(const x of t.split(/\n|\|\|/)){ const y=x.trim().replace(/\.mp4$/i,''); if(y.length>8&&y.length<150&&/[-_]/.test(y)&&!y.includes('【')) names.push(y); } } if(names.length) out.push([r+1,u,[...new Set(names)]]); }
JSON.stringify({PLAN:5,tab:location.search,sheet:sh.name(),uc_col:H[uc],cols:nc.map(c=>H[c]),n:out.length,rows:out,pad:'x'.repeat(60000)});
