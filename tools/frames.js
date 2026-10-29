// 看视频画面用的小工具：在内置浏览器里打开 https://rw9731.github.io/today-growth-dashboard/reports.json ，
// 把这个文件全文作为 javascript_tool 的 text 跑一次，之后：
//   __v.start('thumbs', url, [0.5, 2, 4, 7, 10, 14, 18, 24, 30], '标签')   // 9 张缩略图，看结构、Today 第几秒出现
//   __v.start('bands', [{label, url, times: [0.6, 2.2, 3.8, 5.5]}, ...], 0.7, 0.86)  // 把字幕那一条放大，读开头台词
// 每次 start 之后再跑一次 `await __v.wait()`，返回 [时长, 画布高度] 再 computer screenshot / zoom 看画布。
// 看完 __v.free()。画面在左上角的固定画布里。
window.__v = window.__v || {};
__v.load = (url) => new Promise((res, rej) => { const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.preload = 'auto'; v.style.cssText = 'position:fixed;left:-9999px;top:0;width:200px'; document.body.appendChild(v); v.onloadeddata = () => res(v); v.onerror = () => rej(new Error('video error')); v.src = url; setTimeout(() => rej(new Error('timeout')), 40000); });
__v.seek = (v, t) => new Promise((r) => { let done = false; v.onseeked = () => { if (v.requestVideoFrameCallback) v.requestVideoFrameCallback(() => { done = true; setTimeout(r, 80); }); setTimeout(() => { if (!done) r(); }, 700); }; v.currentTime = Math.min(t, v.duration - 0.1); });
__v.canvas = () => { let c = document.getElementById('__g'); if (!c) { c = document.createElement('canvas'); c.id = '__g'; c.style.cssText = 'position:fixed;left:0;top:0;z-index:2147483647;background:#111'; document.body.appendChild(c); } return c; };
__v.thumbs = async (url, times, label) => { const W = innerWidth, cols = 3, fw = Math.floor(W / cols); const c = __v.canvas(); const v = await __v.load(url); const fh = Math.round(fw * v.videoHeight / v.videoWidth); const rows = Math.ceil(times.length / cols); c.width = W; c.height = rows * (fh + 12); c.style.width = W + 'px'; c.style.height = c.height + 'px'; const x = c.getContext('2d'); x.fillStyle = '#111'; x.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < times.length; i++) { await __v.seek(v, times[i]); const X = (i % cols) * fw, Y = Math.floor(i / cols) * (fh + 12); x.drawImage(v, X, Y + 12, fw, fh); x.fillStyle = '#ff0'; x.font = '10px sans-serif'; x.fillText(label + ' ' + times[i], X + 2, Y + 10); }
  const d = v.duration; v.remove(); return [Math.round(d * 10) / 10, c.height]; };
__v.bands = async (items, y0, y1) => { const W = innerWidth; const c = __v.canvas(); const vids = []; for (const it of items) vids.push([it, await __v.load(it.url)]); const v0 = vids[0][1]; const bh = Math.round(W * (y1 - y0) * v0.videoHeight / v0.videoWidth); const n = items.reduce((s, it) => s + it.times.length, 0);
  c.width = W; c.height = n * (bh + 12); c.style.width = W + 'px'; c.style.height = c.height + 'px'; const x = c.getContext('2d'); x.fillStyle = '#111'; x.fillRect(0, 0, c.width, c.height); let k = 0; const durs = [];
  for (const [it, v] of vids) { for (const t of it.times) { await __v.seek(v, t); const Y = k * (bh + 12); x.drawImage(v, 0, y0 * v.videoHeight, v.videoWidth, (y1 - y0) * v.videoHeight, 0, Y + 12, W, bh); x.fillStyle = '#ff0'; x.font = '10px sans-serif'; x.fillText(it.label + ' ' + t, 3, Y + 10); k++; } durs.push(Math.round(v.duration * 10) / 10); v.remove(); }
  return [durs, c.height]; };
__v.start = (fn, ...args) => { __v.done = null; __v.err = null; __v[fn](...args).then((r) => { __v.done = r; }, (e) => { __v.err = String(e); }); return 'started'; };
__v.wait = async () => { for (let i = 0; i < 40 && !__v.done && !__v.err; i++) await new Promise((r) => setTimeout(r, 1000)); return __v.err ? 'error: ' + __v.err : (__v.done || 'pending'); };
__v.free = () => { const g = document.getElementById('__g'); if (g) g.remove(); };
'frames ready';
