# 每天生成日报

D = 新加坡时间昨天（报告日）。数据：Google 表「国区投放素材」(1LHsOHd5U7Ep0SHF-XQecIE-wj9FN2JireiPFhvp3t0Q)，「投放数据_分日」每天 10:13 左右更新到 D。

1. 读 `'投放数据_分日'!A1:AA` 和 `'素材链接库'!A1:D`（get_values，结果存成文件）。
2. `python3 tools/compute.py --sheet <分日文件> --linklib <链接库文件> --date D --out /tmp/results.json`
   - 输出 `NO_DATA`：表里还没有 D，等 20 分钟再读。
   - `unknown_uc` 不为空：在「✅ Use case 库」找到这些 UC，把 `{"short": 4–8 字简称, "l1": 一级分类, "l2": 二级分类}` 加进 tools/ucs.json，再跑一次。
3. 补链接（要用 Reina 电脑上的内置浏览器，连不上就跳过）：`python3 tools/links_js.py /tmp/results.json --out /tmp/linkjs` 生成几段 JS，每段在它第一行写的飞书页面里用 javascript_tool 跑，返回的 JSON 存成同名 .json；然后 `python3 tools/links_merge.py /tmp/linkjs`，再跑一次第 2 步。原片 = 唯西表「真人原素材」的博主发布链接，成片 = 唯西表「脚本及成片」里那一格，预览 = 唯西日报里的巨量素材视频（每条素材都要有，看板上的「视频」）。
   - 巨量直取（内置浏览器要已登录巨量；跳到登录页就跳过）：`python3 tools/jl_js.py /tmp/results.json --out /tmp/linkjs` 生成 jl.js（只找唯西日报没有视频的，所以要在 yulan.json 存好之后跑）；在 https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825 用 javascript_tool 跑 jl.js 全文，再跑 `await __jlWait()`（没 done 就再跑一次），结果存成 /tmp/linkjs/jl_status.json；然后 `await __jlGet(0)`、`await __jlGet(1)`… 一直到返回 []，把每次返回的数组原样拼成一个，存成 /tmp/linkjs/jl.json（每条带 h 校验码，抄错的链接 links_merge.py 会丢掉）。再跑 links_merge.py。同一个素材 ID 会推到很多账户，tools/jl_hubs.json 里那几个账户基本都有，找不到的再逐个账户搜（最多 100 次）。巨量链接是签名的，2 天过期；唯西日报有永久链接就用唯西的，没有才用巨量的，所以往期页面每天要 `python3 tools/relink.py <日期>` 刷一遍。
4. 扩量分析（也要用内置浏览器，连不上就跳过，看板只显示数字）：`python3 tools/kl_list.py /tmp/results.json --sheet <分日文件>` 列出 D 消耗 ≥ ¥500、notes/D.json 里还没写的扩量家族（最多 4 个），带扩量版和原素材的视频链接。
   - 在内置浏览器开 https://rw9731.github.io/today-growth-dashboard/reports.json ，把 tools/frames.js 全文用 javascript_tool 跑一次；`__v.start('thumbs', 视频, [0.5,2,4,7,10,14,18,24,30], '扩')` → `await __v.wait()` → 截图，看结构、时长、Today 第几秒出现；`__v.start('bands', [...], 0.7, 0.86)` 读开头 0–6 秒字幕。原素材和扩量版各看一遍。
   - 对照唯西「扩量素材迭代排期」(?sheet=kMJdAv) 里这条的「怎么改」。
   - 写进 notes/D.json：`{原素材名: {"title": "UC 简称 + 类型（UC 编号）", "changed": "改了什么", "why": "为什么跑上来"}}`。一句话一件事，要具体（时长、开头那句、Today 出现时间），不写套话；样本小就直说。
5. `python3 tools/build.py /tmp/results.json`：写 D/index.html，更新 reports.json；D 是最新一天时同时改 index.html。
6. 提交 D/、index.html、reports.json、tools/links.json、notes/（和改过的 tools/ucs.json），push 到 main。

已经发布的日子只补链接、不重算：`python3 tools/relink.py YYYY-MM-DD [--sheet <分日文件>]`（带 --sheet 会补素材类型）。

口径：消耗看 D；次留率、次留成本看 D-3 到 D-1 激活的人（巨量次留记在回访那天）；标签和全盘三天比。门槛在 compute.py 的 TH。
