# 每天生成日报

D = 新加坡时间昨天（报告日）。数据：Google 表「国区投放素材」(1LHsOHd5U7Ep0SHF-XQecIE-wj9FN2JireiPFhvp3t0Q)，「投放数据_分日」每天 10:13 左右更新到 D。

1. 读 `'投放数据_分日'!A1:AA` 和 `'素材链接库'!A1:D`（get_values，结果存成文件）。
2. `python3 tools/compute.py --sheet <分日文件> --linklib <链接库文件> --date D --out /tmp/results.json`
   - 输出 `NO_DATA`：表里还没有 D，等 20 分钟再读。
   - `unknown_uc` 不为空：在「✅ Use case 库」找到这些 UC，把 `{"short": 4–8 字简称, "l1": 一级分类, "l2": 二级分类}` 加进 tools/ucs.json，再跑一次。
3. 补链接（要用 Reina 电脑上的内置浏览器，连不上就跳过）：`python3 tools/links_js.py /tmp/results.json --out /tmp/linkjs` 生成几段 JS，每段在它第一行写的飞书页面里用 javascript_tool 跑，返回的 JSON 存成同名 .json；然后 `python3 tools/links_merge.py /tmp/linkjs`，再跑一次第 2 步。原片 = 唯西表「真人原素材」的博主发布链接，成片 = 唯西表「脚本及成片」里那一格，预览 = 唯西日报里的巨量素材视频（每条素材都要有，看板上的「视频」）。
   - 巨量直取（内置浏览器要已登录巨量；跳到登录页就跳过）：`python3 tools/jl_js.py /tmp/results.json --out /tmp/linkjs --sheet <分日文件>` 生成 jl.js（只找唯西日报没有视频的，所以要在 yulan.json 存好之后跑）；在 https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825 用 javascript_tool 跑 jl.js 全文，再跑 `await __jlWait()`（没 done 就再跑一次），结果存成 /tmp/linkjs/jl_status.json；然后 `await __jlGet(0)`、`await __jlGet(1)`… 一直到返回 []，把每次返回的数组原样拼成一个，存成 /tmp/linkjs/jl.json（每条带 h 校验码，抄错的链接 links_merge.py 会丢掉）。再跑 links_merge.py。同一个素材 ID 会推到很多账户，tools/jl_hubs.json 里那几个账户基本都有，找不到的再逐个账户搜（最多 100 次）。巨量链接是签名的，2 天过期；唯西日报有永久链接就用唯西的，没有才用巨量的，所以往期页面每天要 `python3 tools/relink.py <日期>` 刷一遍。
4. 扩量分析（也要用内置浏览器，连不上就跳过，看板只显示数字）：`python3 tools/kl_list.py /tmp/results.json --sheet <分日文件>` 列出 D 消耗 ≥ ¥500、notes/D.json 里还没写的扩量家族（最多 4 个），带扩量版和原素材的视频链接。
   - 在内置浏览器开 https://rw9731.github.io/today-growth-dashboard/reports.json ，把 tools/frames.js 全文用 javascript_tool 跑一次；`__v.start('thumbs', 视频, [0.5,2,4,7,10,14,18,24,30], '扩')` → `await __v.wait()` → 截图，看结构、时长、Today 第几秒出现；`__v.start('bands', [...], 0.7, 0.86)` 读开头 0–6 秒字幕。原素材和扩量版各看一遍。
   - 对照唯西「扩量素材迭代排期」(?sheet=kMJdAv) 里这条的「怎么改」。
   - 对原素材的字幕，开头和后面都要对（后面至少对 3 句），按改法写：开头和后面的口播都和原素材不一样，写「全片重配」（画面用原片镜头）；只有开头几句是新写新配的、后面照原片，写「换开头」；没新写台词，只删减、调顺序、把原句挪到开头，写「只剪辑」；AI 照一条素材重新生成，写「AI 重拍」。changed 第一句就写是哪种。
   - 改法写进 tools/gaifa.json：`{素材ID: {"gaifa": "原片/只剪辑/换开头/全片重配/AI 重拍", "checked": "对的日期", "note": "一句依据"}}`。要对的清单：`python3 tools/gaifa_list.py /tmp/results.json --sheet <分日文件>`（D 消耗 ≥ ¥500、gaifa.json 里还没有的二剪，带它和父素材或原片的视频；第 3 步跑 jl_js.py 时加 `--sheet <分日文件>`，缺的视频会一起从巨量拿）。parent_id 为空 = 原片没在巨量投过，对不了，跳过，看板上显示「二剪（未核对）」。写完再跑一次第 2 步。
   - 写进 notes/D.json：`{原素材名: {"title": "UC 简称 + 类型（UC 编号）", "changed": "改了什么", "why": "为什么跑上来"}}`。一句话一件事，要具体（时长、开头那句、Today 出现时间），不写套话；样本小就直说。
5. `python3 tools/build.py /tmp/results.json`：写 D/index.html，更新 reports.json；D 是最新一天时同时改 index.html。
6. 提交 D/、index.html、reports.json、tools/links.json、tools/gaifa.json、notes/（和改过的 tools/ucs.json），push 到 main。

已经发布的日子只补链接、不重算：`python3 tools/relink.py YYYY-MM-DD [--sheet <分日文件>]`（带 --sheet 会补素材类型）。

口径：消耗看 D；次留率、次留成本看 D-3 到 D-1 激活的人（巨量次留记在回访那天）；标签和全盘三天比。门槛在 compute.py 的 TH。

## 七、核心 insight 和下一步（Reina 10/31 加）

compute.py 会自动算出 use case 分层（plan_uc）、每周产能分配（plan_cap）和剪辑手法对比（plan_method）：
- T1 主攻 = 四天消耗占全盘 ≥ 3%，且次留率不低于、次留成本不高于三天全盘；T2 次优先 = 占 0.8% 到 3%、三天激活 ≥ 60，次留率不低于全盘、次留成本不超过全盘 1.1 倍；T3 = 过了 3% 但次留不达标；其余是测新 / 观察。
- 产能（每周）：维系 120 条 AI 素材、100 条 KOC/KOL 二创或重配；agency ≥ 50 条真人原片。T1 55%、T2 20%、T3 20%、测新 5%。层内按 use case 四天消耗开根号分，再按这个 use case 里哪种供给次留更便宜分到 AI / 二创 / 原片。门槛和比例在 compute.py 的 CAP、TIER_SHARE、PLAN_TH。

每天在 build.py 之前写 `notes/D-plan.json`（数字都从 /tmp/results.json 里取，写完核对一遍）：
```
{"headline": "一句话结论",
 "points": [{"t": "粗体短结论", "d": "证据：具体数字", "a": "动作：做几条、做什么、停什么"}],   // 3 到 5 条
 "supply": "产能安排补充（可用 <b>）", "method": "剪辑手法结论（可用 <b>）",
 "uc": {"UC_ID": "这个 use case 下一步具体做什么"}}   // T1、T2、T3 每个都写，测新里花得多的也可以写
```
写法：sharp、短，不写套话，每条都要有数和动作。重点看：哪个 use case 进出了 T1；同一个 use case 里 AI / 二创 / 原片 谁的次留更便宜（该把产能挪过去）；哪种改法次留便宜（全片重配、换开头、只剪辑、AI）；T3 里次留率低（承接问题，交产品）还是只是贵（做变式）；扩量分析里看到的做法能不能复制到别的 use case；「待对应」这类没对上 UC 的消耗有多大。动作要落到条数和渠道上，和看板算出的排产一致。全程中文，不用破折号。
