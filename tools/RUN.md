# 每天生成日报

D = 新加坡时间昨天（报告日）。数据：Google 表「国区投放素材」(1LHsOHd5U7Ep0SHF-XQecIE-wj9FN2JireiPFhvp3t0Q)，「投放数据_分日」每天 10:13 左右更新到 D。

1. 读 `'投放数据_分日'!A1:AB` 和 `'素材链接库'!A1:D`（get_values，结果存成文件）。
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

口径：消耗看 D；次留率、次留成本看 D-3 到 D-1 激活的人（巨量次留记在回访那天）；连续 3 留率、成本看 D-5 到 D-3 激活的人（AB 列「3日留存」按激活日记，约 3 天才稳，10/16 起有数）；标签和分层只看次留。四、昨天消耗排行只列昨天消耗 ¥1,000 以上的素材（TH 的 rank）。门槛在 compute.py 的 TH。

连续 3 留怎么读（Reina 11/2 定看板改名，日报和周报都适用，优先于任务说明里的旧说法）：
- 一律写「连续 3 留」，不写「3 留」「3 日留存」。Google 表 AB 列表头还叫「3日留存」，脚本按这个名字读，不要改。
- 定义：巨量 attribution_retention_3d_cnt。我们回传 retention_3d 的条件是 D1、D2、D3 每天都打开（today-cloud 的 oceanengine-retention-events.ts；RFC 写明当天留存不上报）。
- 不是 Daily Insight 里第 3 天当天回来的 D3。10/27–29 激活：看板 8.6%，日报广告投放 19.8%。两边不能直接比。
- 只比素材和 use case 之间的相对高低。不写「真实留存」「留得住」「留不住」。
- 对不是天天用的 use case 偏低，不能单凭它停量、不加量或判好坏，要和次留、次留成本一起看。
- 次留和日报定义相同，巨量回传会漏一部分，通常低几个百分点。团队看留存水平用 Daily Insight。

## 七、核心 insight 和下一步（Reina 10/31 定，日报口径，不排每周产能）

compute.py 自动算：
- `plan_uc`：每个 use case 的分层和前 5 个报告日的分层（hist、streak、change），和前一天比的次留率、次留成本变化（d_rate、d_cpr），各供给（AI / 二创 / 原片）的次留成本和次留率。
- 分层：T1 主攻 = 四天消耗占全盘 ≥ 3%，次留率不低于、次留成本不高于全盘；T2 次优先 = 占 0.8% 到 3%、三天激活 ≥ 60，次留率不低于全盘、次留成本不超过全盘 1.1 倍；T3 = 过了 3% 但次留不达标；其余是观察。门槛在 compute.py 的 PLAN_TH。
- `plan_method`：按改法合并的次留成本和次留率。

每天在 build.py 之前写 `notes/D-plan.json`：
```
{"headline": "一句话结论",
 "global": [{"t": "粗体结论", "d": "证据（可用 <b>）"}],   // 全局 insight：整盘的钱、次留和连续 3 留往哪走（连续 3 留看 overview 的 rate3_w、cpr3_w、rate3_days，各表的 rate3、cpr3），2 到 4 条
 "next":   [{"t": "动作", "d": "依据和怎么做"}],           // 下一步行动：今明两天能做的小步（停什么、加几条什么、等什么），3 到 5 条
 "delta":  [{"t": "变化", "d": "和昨天比的数"}],           // 今天的变化：进出 T1、某个渠道翻转、某条素材拖累，2 到 4 条
 "steady": [{"t": "规律", "d": "连续几天的数"}],           // 一直成立的：连续 3 天以上不变的，2 到 4 条
 "method": "剪辑手法一句（可用 <b>）",
 "uc": {"UC_ID": "这个 use case 下一步具体做什么"}}
```
写法：日报口径，不排每周产能，动作按小步快跑写（今天停、明天加两三条、等次留再定）。每条都要有数。delta 和 steady 要拿前几天的数比：用同样参数跑 compute.py --date D-1、D-2 到别的文件（只读取，不发布）。样本小的（激活不到 50）直说样本小，不当结论。sharp、短，不写套话。全程中文，不用破折号。

## 周报（每周一，Reina 11/1 定）

页面和 notes 不写 T1、T2、T3 这些代号（Reina 11/2 定），写大白话：能放量、留存好；量中等、留存好；能放量、留存不达标；量小，先观察。头部素材表不放脚本，脚本和分析放第六部分。
页面是给公司看的报告：不写电脑没连上、几条没读脚本、脚本 bug、口径修正这类过程信息，这些只放推送和最后回复。页面和 notes 不只写 use case 编号，要写名字。「继续扩量的 use case」和二创素材的标签写全：一级分类 + UC_ID + 中文简称（页面按 uc、tag 字段自动带出）。

M = 上周一。数据要等「投放数据_分日」更新到周日（周一 10:13 左右）。

1. 读 `'投放数据_分日'!A1:AB`（存成文件），`python3 tools/week.py --sheet <分日文件> --week M --out /tmp/week.json`。输出 `NO_DATA` 就是周日还没出。
2. 读全片脚本（见下面「读全片脚本」）：`python3 tools/script_todo.py --week /tmp/week.json --out /tmp/sc`，范围是周消耗 ≥ ¥2,000 的所有素材，脚本库里没有的都要读。
3. 看 /tmp/week.json 和 scripts/ 写 `notes/week-M.json`：
```
{"headline": "一句话结论",
 "insight": [{"t": "结论", "d": "证据（可用 <b>）"}],                       // 核心 insight 3 到 5 条
 "scale":  [{"uc": "WK05", "t": "动作", "d": "依据和下周具体怎么加"}],      // 继续扩量的 use case：T1 和差一点进 T1、T2 里留存好的，2 到 4 个
 "drop":   [{"uc": "SH02", "t": "动作", "d": "依据"}],                        // 不要再加的 use case：能放量但留存不达标里最差的、量小且留不住的、Use case 库里已暂停还在花钱的，3 到 6 个，同时显示在第三部分表里的「留存差，不要再加」
 "remix":  [{"id": "素材ID", "tag": "UC_ID", "t": "素材简称（类型）", "d": "数据", "how": "为什么好、二创怎么做"}],  // 拿去二创的，从 top 里挑 2 到 4 条，优先 pick=true
 "stop":   [{"t": "动作", "d": "依据"}],                                    // 停掉或降预算，2 到 4 条，优先 bad 里多花的钱最多的
 "other":  [{"t": "动作", "d": "依据"}],                                    // 产能、口径、要谁跟进，1 到 3 条
 "uc": {"UC_ID": "这个 use case 下周做什么"},                               // 表里 T1、T2、T3 每个一句
 "l1": {"一级分类": "这个分类下周做什么，一句"},                          // 第二部分「一级分类」，周消耗占比 ≥ 0.5% 的每个写一句
 "wk_market": [{"t": "结论", "d": "依据，要和上周周末比"}], "wk_top": [{"t": "结论", "d": "依据和下周怎么试"}], "wk_names": {"素材ID": "头部素材短名"},  // 第一部分「周中和周末」，分大盘和头部素材，先写结论再写依据，小标题必须是一句结论，不能只写一个词；先按上线天数拆（wk.age）、看同一批素材过周末（wk.carry、wk.batch），再下分类结论，新老素材混着看会把新素材的跌算到分类头上；周五激活的人周六回访，周五也算周末；上周周中被单日拉低要说明，不能只比均值；说放量造成要有同批素材加量才跌的证据；每个一级分类写清老素材和新素材各自怎么变，标签用老素材好、新素材跌、新老都跌、两条拉高、样本小（四个字以内）；老素材好要先去掉最大的一两条再看；"wk_tags": {"一级分类或素材ID": "周末多投/周末压/看不出/样本小"}
 "rules_note": "规律的依据范围一句",
 "rules": [{"t": "规律 + 下周怎么做", "d": "依据：每组多少条、次留率、次留成本、连续 3 留，少于 5 条的只说方向"}],  // 第六部分「头部和拖后腿素材的规律」，3 到 6 条，不摆脚本
 "output": {"note": "各类型按什么日期算", "rows": [{"t": "类型", "n": 产出, "plan": 计划, "live": 上线投放}]},  // 素材产出数量，放第五部分。小红书、抖音从「Today KOL/KOC 视频」按发布日期数；AI、唯西星图达人、自建号、星广按唯西表和素材产出日报；二创和上线投放从「投放数据_分日」按首次消耗数；计划按素材产出日报，二创计划按「每周素材追踪」
 "top_use": {"素材ID": "十来个字：继续投、小量试、修好再扩"}}               // top 里没进 remix 的每条，放在头部素材表
```
4. `python3 tools/build_week.py /tmp/week.json`：写 week/M/index.html、week/index.html（最新一周）、weeks.json。
5. 提交 week/、weeks.json、notes/week-M.json，push。

口径：消耗看整周；次留看周一到周六激活（周日的次留下周才出）；连续 3 留看周一到周四激活。门槛在 week.py 的 WTH：能放量的 use case = 周消耗 ≥ 全盘 3% 且 ≥ ¥20,000；头部素材 = 这周有一天消耗 ≥ ¥2,000、激活 ≥ 100、次留率和次留成本都好于全盘，不限条数（Reina 11/2 定）；拖后腿 = 周消耗 ≥ 全盘 1%（最少 ¥5,000）但次留率 < 全盘 85% 或次留成本 > 1.2 倍，按多花的钱排，最多 8 条。pick = 次留率高全盘 5% 以上、次留成本低 10% 以上（连续 3 留不进这条规则）。

## 读全片脚本（日报、周报都要做，Reina 11/1 定）

每条投放素材读一次全片字幕，存成 scripts/<素材ID>.json（格式见 tools/scripts_lib.py），以后日报、周报都直接用。日报、周报的素材表都不放脚本（Reina 11/2 定），脚本只用在后面的分析里：notes 里引用开头原话和结构，compute.py 和 week.py 按 Today 第几秒出现、开头怎么钩、形式、时长分组算次留（patterns，页面「脚本规律」）。

- 要读哪些：日报 `python3 tools/script_todo.py --daily /tmp/results.json --out /tmp/sc`（「四、昨天消耗排行」全部、拖后腿和次留好但贵的、扩量和它们的原素材）；周报 `--week /tmp/week.json`（周消耗 ≥ ¥2,000 的全部）。已经读过的不重读。写 /tmp/sc/todo.json 和 /tmp/sc/jl.js。
- 必须用 Reina 电脑上的内置浏览器读，不读不写分析。todo 超过 12 条就拆成 2 到 4 批，用 Agent 工具并行跑，每个 agent 用自己开的 tab（tabs_create，第一个没面板就 preview_start），只写 scripts/ 下自己那批的文件。
- 每个 tab：navigate 到巨量素材页 https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825 （网址里有 login 就停，不输入账号密码）；resize_window 1000x2000；跑这一批的 jl.js（`python3 tools/script_todo.py ... --out` 生成后可以按批拆：同一段 JS 只换 NEED 列表），`await __jlWait()` 到 done；再跑 tools/frames.js 全文。
- 每条：先 `__v.start('thumbs', 链接, [0.5,3,6,10,15,20,30,40,50], '标签')` 看整画面（字幕在多高、形式、Today 第几秒出现）；再 `__v.start('script', 链接, '标签', step, y0, y1, 3)` 读全片字幕，y0、y1 按字幕高度取，字幕一秒一换的 step 用 1；截图只有约 750 像素高，画布更高就 `__v.page(1)`、`__v.page(2)` 每次下翻 700 像素再截。链接用 `__jl.res[ID].u`，没有就用 todo.json 的 video_permanent。
- note 里写看到的问题：字幕打码、「审核」「DEMO」「样片」或平台水印（第几秒）、Today 界面露出 bug 或内部字样、App 名不是 Today、隐私露出、素材名和内容对不上、活动口径（永久免费、送 Token、Pro 权益）。
- 做完 resize_window preset desktop，关掉自己的 tab。
