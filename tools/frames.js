// 看视频画面用的小工具：在内置浏览器里打开 https://rw9731.github.io/today-growth-dashboard/reports.json （或巨量素材页，那里能直接用 __jl.res[ID].u），
// 先 resize_window 到 1000x2000（一屏能装下整条视频的字幕），把这个文件全文作为 javascript_tool 的 text 跑一次。
// 读全片脚本（Reina 11/1：每条都要读全片字幕）：
//   __v.start('script', url, '标签')            // 默认每 2 秒一格、3 列、截画面 47% 到 80% 那一条，按列从上往下读。先用 thumbs 看整画面找字幕在多高，再定 y0、y1；字幕一秒一换的 step 用 1
//   await __v.wait()                             // 返回 [时长, 格数, 画布高度]；画布比截图高就 __v.page(1)、__v.page(2) 每次往下翻 700 像素再截（截图大约只有 750 像素高）
//   字幕不在这条（截出来没字）就换 y0、y1：__v.start('script', url, '标签', 2, 0.3, 0.6) 或 (2, 0.75, 0.95)
// 其他：__v.start('thumbs', url, [0.5, 2, 4, 7, 10, 14, 18, 24, 30], '标签') 9 张整画面；
//   __v.start('bands', [{label, url, times: [...]}, ...], 0.7, 0.86) 两条视频的字幕放一起对照（对改法用）。
// 每次 start 之后 await __v.wait() 再 computer screenshot / zoom。看完 __v.free()，最后 resize_window preset desktop 复原。
window.__v = window.__v || {};
if (!window.innerWidth || window.innerWidth < 400) Object.defineProperty(window, 'innerWidth', {get: () => document.documentElement.clientWidth || 800, configurable: true});
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
// 结构：12 张小图一屏（6 列），看形式、Today 第几秒出现、录屏时段。
__v.strip = async (url, times, label) => { const W = innerWidth, cols = 6, fw = Math.floor(W / cols); const c = __v.canvas(); const v = await __v.load(url); const fh = Math.round(fw * v.videoHeight / v.videoWidth); const rows = Math.ceil(times.length / cols); c.width = W; c.height = rows * (fh + 12); c.style.width = W + 'px'; c.style.height = c.height + 'px'; c.style.top = '0px'; const x = c.getContext('2d'); x.fillStyle = '#111'; x.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < times.length; i++) { if (times[i] > v.duration) continue; await __v.seek(v, times[i]); const X = (i % cols) * fw, Y = Math.floor(i / cols) * (fh + 12); x.drawImage(v, X, Y + 12, fw, fh); x.fillStyle = '#ff0'; x.font = '10px sans-serif'; x.fillText(label + ' ' + times[i] + 's', X + 2, Y + 10); }
  const d = v.duration; v.remove(); return [Math.round(d * 10) / 10, c.height]; };
// 全片字幕：从 0.4 秒起每 step 秒截一条带，cols 列排满整片（按列从上往下读）。返回 [时长, 格数, 画布高度]。
// 画布比屏幕高时把 __g 的 style.top 设成负数分屏截图。
__v.script = async (url, label, step, y0, y1, cols) => { step = step || 2; y0 = y0 == null ? 0.47 : y0; y1 = y1 == null ? 0.80 : y1; cols = cols || 3; const W = innerWidth, cw = Math.floor(W / cols); const c = __v.canvas(); const v = await __v.load(url); const bh = Math.round(cw * (y1 - y0) * v.videoHeight / v.videoWidth); const times = []; for (let t = 0.4; t < v.duration; t += step) times.push(Math.round(t * 10) / 10); const rows = Math.ceil(times.length / cols);
  c.width = W; c.height = rows * (bh + 11); c.style.width = W + 'px'; c.style.height = c.height + 'px'; c.style.top = '0px'; const x = c.getContext('2d'); x.fillStyle = '#111'; x.fillRect(0, 0, c.width, c.height);
  for (let i = 0; i < times.length; i++) { await __v.seek(v, times[i]); const col = Math.floor(i / rows), row = i % rows; const X = col * cw, Y = row * (bh + 11); x.drawImage(v, 0, y0 * v.videoHeight, v.videoWidth, (y1 - y0) * v.videoHeight, X, Y + 11, cw - 2, bh); x.fillStyle = '#ff0'; x.font = '10px sans-serif'; x.fillText(label + ' ' + times[i] + 's', X + 2, Y + 9); }
  const d = v.duration; v.remove(); return [Math.round(d * 10) / 10, times.length, c.height]; };
__v.page = (k, px) => { const g = document.getElementById('__g'); if (g) g.style.top = (-k * (px || 700)) + 'px'; return k; };
__v.start = (fn, ...args) => { __v.done = null; __v.err = null; __v[fn](...args).then((r) => { __v.done = r; }, (e) => { __v.err = String(e); }); return 'started'; };
__v.wait = async () => { for (let i = 0; i < 40 && !__v.done && !__v.err; i++) await new Promise((r) => setTimeout(r, 1000)); return __v.err ? 'error: ' + __v.err : (__v.done || 'pending'); };
__v.free = () => { const g = document.getElementById('__g'); if (g) g.remove(); };
'frames ready';
