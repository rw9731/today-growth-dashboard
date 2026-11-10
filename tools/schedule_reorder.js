// args: TAB, S(1-based region start), KEEP(rows above S with same-day content: {MMDD: firstRow}), SHIFT(old ref >= SHIFT_AT -> -SHIFT), WRITE
const sh=window.spread.getActiveSheet();if(sh.id()!==TAB)throw new Error('tab '+sh.id());
const N=sh.getRowCount(),C=Math.min(sh.getColumnCount(),19);
const rows=[];for(let r=S-1;r<N;r++){const v=[];for(let c=0;c<C;c++)v.push(sh.getText(r,c)||'');rows.push({r:r+1,v})}
const has=x=>x.v.some((t,i)=>i!==12&&t.trim());
const last=rows.filter(has).pop().r;const R=rows.filter(x=>x.r<=last);
if(R.some(x=>[13,14,15,16,17,18].some(i=>i<C&&x.v[i].trim())))throw new Error('有人填了素材名/成片，停');
const WD='日一二三四五六';
let day='',items=[],intro=null;
for(const x of R){const h=x.v[0].trim();
 if(/说明/.test(h)){intro=x;continue}
 if(h){const m=/^(\d{1,2})\/(\d{1,2})/.exec(h);day=m?String(m[1]).padStart(2,'0')+String(m[2]).padStart(2,'0'):(/下周/.test(h)?'9999':day)}
 if(!has(x))continue;
 let d=day;if(/顺延到下周/.test(x.v[10]))d='9999';
 const t=/【二创/.test(x.v[10])?1:0;
 items.push({x,d,t})}
items.forEach((o,i)=>o.i=i);
items.sort((a,b)=>a.d.localeCompare(b.d)||a.t-b.t||a.i-b.i);
const out=[];let pd=null;
for(const o of items){if(o.d!==pd&&o.d>='1111'&&intro&&!out.includes(intro)){out.push(intro)}pd=o.d;out.push(o)}
const map={};out.forEach((o,k)=>{const x=o.x||o;map[x.r]=S+k});
const shift=n=>n>=SHIFT_AT?n-SHIFT:n;
const remap=n=>{const c=shift(n);return map[c]||c};
const fix=s=>s.replace(/第 ?(\d+)((?: ?[-–、,，] ?\d+)*) ?行/g,(m,a,rest)=>'第 '+remap(+a)+rest.replace(/\d+/g,q=>remap(+q))+' 行');
// 每天的标题
const lab={};for(const o of items){const L=(lab[o.d]??={ai:0,ec:0,v:0});const n=parseInt(o.x.v[9])||0;if(o.t)L.ec+=n;else L.ai+=n;if(/头部模板|同脚本换画面/.test(o.x.v[10])&&!/顺延/.test(o.x.v[10]))L.v+=n}
const head=d=>{const L=lab[d];if(d==='9999')return `下周（11/10 晚顺延，这周先不做，共 ${L.ai+L.ec} 条）`;const dt=new Date(2026,+d.slice(0,2)-1,+d.slice(2));const s=`${+d.slice(0,2)}/${+d.slice(2)} 周${WD[dt.getDay()]}`;
 if(KEEP[d])return `${s}（续：这天上面第 ${KEEP[d]} 行起还有；这里 AI ${L.ai} 条、二创 ${L.ec} 条）`;
 return `${s}（AI ${L.ai} 条、二创 ${L.ec} 条，共 ${L.ai+L.ec} 条；其中头部模板变式 ${L.v} 条）`};
const NEW=out.map((o,k)=>{if(!o.x){const v=o.v.slice();v[10]=fix(v[10]);return v}const v=o.x.v.slice();v[0]=(k===0||out[k-1].d!==o.d)?head(o.d):'';for(const c of [8,10,11])v[c]=fix(v[c]);return v});
const total=last-S+1;let w=0;
if(WRITE){for(let k=0;k<total;k++){const r=S-1+k,v=NEW[k]||Array(C).fill('');for(let c=0;c<C;c++){if(c===12)continue;const cur=sh.getText(r,c)||'';const nv=v[c]||'';if(cur!==nv){sh.setCellValue(r,c,nv);w++}}}}
[last,out.length,w,Object.entries(map).map(([a,b])=>a+'>'+b).join(','),NEW.map((v,k)=>v[0]?(S+k)+':'+v[0]:'').filter(Boolean).join(' | ')]
