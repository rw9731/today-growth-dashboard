# 每天生成日报

## 激活和次留口径（Reina 11/4 定）

激活 = 巨量转化数（计费时间），次留 = 深度转化数（计费时间），都记在计费当天，次留率 = 深度转化数 ÷ 转化数。
compute.load_rows 的 shift_ret 把 ret 往后挪一天喂给原来的算法，所以 results 里看到的日期窗口含义不变（D 天 cohort）；不要再自己挪一次。
10/11 以来的表已重算。10/27 到 11/3 的日报页面和 notes 11/5 已按这个口径和当时的现行规则重算（Reina 要求），周报 week/2026-10-26 还是旧口径（激活 active，次留 next_day_open）。

D = 新加坡时间昨天（报告日）。数据：Google 表「国区投放素材」(1LHsOHd5U7Ep0SHF-XQecIE-wj9FN2JireiPFhvp3t0Q)，「投放数据_分日」由定时任务「巨量投放数据日更」写，11/4 起它 06:51 开跑，07:20–07:40 更新到 D。

1. 读 `'投放数据_分日'!A1:AB` 和 `'素材链接库'!A1:D`（get_values，结果存成文件）。再读 `'✅ Use case 库'!A1:G200` 存成文件，跑 `python3 tools/sync_ucs.py <库文件>` 同步简称（库里 Use case 写成「简称：描述」，第一个冒号前就是简称，Reina 11/4 定，不手改 ucs.json）。输出 changed 不为空要写进最后回复，no_colon 不为空说明库里有 Use case 没写简称，告诉 Reina。
2. `python3 tools/compute.py --sheet <分日文件> --linklib <链接库文件> --date D --out /tmp/results.json`
   - 输出 `NO_DATA`：表里还没有 D，等 20 分钟再读。
   - `unknown_uc` 不为空：先确认库里有这些 UC，再跑一次 sync_ucs.py；库里没有的告诉 Reina，不自己起名字。
3. 补链接（要用 Reina 电脑上的内置浏览器，连不上就跳过）：`python3 tools/links_js.py /tmp/results.json --out /tmp/linkjs` 生成几段 JS，每段在它第一行写的飞书页面里用 javascript_tool 跑，返回的 JSON 存成同名 .json；然后 `python3 tools/links_merge.py /tmp/linkjs`，再跑一次第 2 步。原片 = Reina 新表「today ai koc kol 真人原素材」(https://my.feishu.cn/wiki/Z85OwlT9iion1Xk2ASAc9xcGnTs) 的「素材发布链接」，成片 = 唯西表「脚本及成片」里那一格，预览 = 唯西日报里的巨量素材视频（每条素材都要有，看板上的「视频」）。
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

## 简称（Reina 11/4 定，日报、周报、排期看板都一样）

库里 Use case 列写成「简称：描述」，第一个冒号前就是简称。每次跑之前用 tools/sync_ucs.py 从库同步，页面和 notes 都用这个简称，不自己换说法。周报第 1 步同样先同步。
`_meta.banned` 里的词（重排、重新排，Reina diss 过很多遍）不写进简称，也不写进 notes。素材原名和视频字幕原话照实留着，不改（素材名是跟巨量和飞书匹配用的，字幕是视频里真实的话）；字幕里有这个词的，脚本 note 里提一句。

PS03 工作和孩子（Reina 11/4 定）：「在微信里直接跟Today对话」这条线并进 PS03，素材映射 I 列按内容标，只有工作的归 WK02，老板语音、合作方、一个人住归 PS01。PS03 按「子方向」看三部分：接娃和班级群、消息排清单、孩子的具体问题。新素材按字幕内容判，不按素材名继承。

## 判差第几天（Reina 11/4 定，日报第四节和第五节）

compute.py 的 bad_streak 自动算，每条素材写进 bad_n、bad_first、bad_after、bad_up，不用手填。
- 时间：D 激活的人 D+1 才有次留，表 D+2 上午才看得到。所以 x 这天上午看的是 x-4 到 x-2 激活的人，第 1 天从看得到那天上午算，不追之前花的钱。
- 判差：这 3 天激活合计至少 50 人，且次留率低于同期全盘的 80%，或次留成本高于同期全盘的 1.25 倍。和同期全盘比，周末已经扣掉。门槛在 compute.py 的 TH（judge_act、low、high、stuck_n、stuck_cost）。
- 第四节「判差」列写连续第几天。第五节「判差 3 天以上还在花」列连续 3 天及以上、昨天还花 ¥200 以上的；D 的消耗比第一次判差那天高 50% 以上且至少 ¥500，标「判差后放量」。
- 表里只有消耗，没有开关状态：掉量可能是关了，也可能是系统不跑了。没读过巨量投放状态前，不写「代理没关」。

## 七、核心 insight 和下一步（Reina 10/31 定，日报口径，不排每周产能）

compute.py 自动算：
- `plan_uc`：每个 use case 的分层和前 5 个报告日的分层（hist、streak、change），和前一天比的次留率、次留成本变化（d_rate、d_cpr），各供给（AI / 二创 / 原片）的次留成本和次留率。
- 次留好的标准（Yitao、Reina 11/4 定）：次留率和次留成本都比大盘均值好才算，大盘就是同窗口全盘。优先级次留率高于次留成本，写分析时有分歧先看次留率。要定期提高要求时改 compute.py 的 GOOD_RATE。之前写过的至少 30% 不再用。
- 素材和 use case 的标签日报周报同一套说法，见「标签」一节，不写单独的一般、拖后腿当标签。
- 分层：T1 主攻 = 四天消耗占全盘 ≥ 3%，次留好且次留成本不高于全盘；T2 次优先 = 占 0.8% 到 3%、三天激活 ≥ 60，次留好且次留成本不高于全盘；T3 = 过了 3% 但次留不达标；其余是观察。门槛在 compute.py 的 PLAN_TH。
- `plan_method`：按改法合并的次留成本和次留率。

每天在 build.py 之前写 `notes/D-plan.json`：
```
{"headline": "一句话结论",
 "global": [{"t": "粗体结论", "d": "证据（可用 <b>）"}],   // 全局 insight：整盘的钱、次留和连续 3 留往哪走（连续 3 留看 overview 的 rate3_w、cpr3_w、rate3_days，各表的 rate3、cpr3），2 到 4 条
 "next":   [{"t": "动作", "d": "依据和怎么做"}],           // 下一步行动：今明两天能做的小步（停什么、加几条什么、等什么），3 到 5 条
 "delta":  [{"t": "变化", "d": "和昨天比的数"}],           // 今天的变化：进出 T1、某个渠道翻转、某条素材拖累，2 到 4 条
 "steady": [{"t": "规律", "d": "连续几天的数"}],           // 一直成立的：连续 3 天以上不变的，2 到 4 条
 "method": "剪辑手法一句（可用 <b>）",
 "uc": {"UC_ID": "这个 use case 下一步具体做什么"},
 "angles": [...]}                                       // 扩量角度建议，每天都要写，格式见下面「扩量角度建议」
```
写法：日报口径，不排每周产能，动作按小步快跑写（今天停、明天加两三条、等次留再定）。每条都要有数。delta 和 steady 要拿前几天的数比：用同样参数跑 compute.py --date D-1、D-2 到别的文件（只读取，不发布）。样本小的（激活不到 50）直说样本小，不当结论。sharp、短，不写套话。全程中文，不用破折号。

## 扩量角度建议（Reina 11/3 定，日报、周报都写）

页面位置：日报「四、昨天消耗排行」最下面，周报「四、头部素材和拖后腿的素材」头部素材表下面（id="angles"）。飞书给唯西的快照也要带这一块，所以这里的内容按给素材团队看来写。

写进 notes/D-plan.json（周报是 notes/week-M.json）的 `angles`，build 之前写好。数据行（占比、次留率、次留成本、按供给）和素材类型那一行页面自动算，不用写：
```
"angles": [{"uc": "LG02",
            "why": "一句判断：这个 use case 靠什么撑起来，往哪拓。带素材原名和数，数字写时间范围",
            "shot": "已拍过的角度，顿号分开",
            "items": [{"s": "角度", "sup": "AI 或 二创", "d": "具体场景，分号分开，可以不写", "sched": "M/D，只有排期里有才写"}]}]
```
- 写哪些 use case：当天「能放量、留存好」的全写；「量中等、留存好」里连续 3 天以上的写；最近一份周报 scale 里的也写，窗口含周末掉出去的在 why 里写清。排期里正在测新方向的 use case 也可以写，why 里写清量小（比如 WK06 的行业简报）。按消耗占比从大到小排。
- 角度从哪来：先读「✅ Use case 库」的「可包装的场景」，这是角度池；再看 scripts/ 和 mat 里这个 use case 拍过什么。拍过的进 shot，没拍过的进 items，不要把拍过的再列一遍。可以加库里没有的新角度，加了就在推送和最后回复里写一句，由 Reina 定要不要进库。
- 选角度看三点：人够多（大多数人都会遇到，不限某个职业）；有明天回来的理由（天天或每周都有）；下载当天就能演出片里那一下。要对照「产品能力进度」，做不到的不列。
- sched：读唯西「扩量素材迭代排期」(?sheet=kMJdAv) 和「新素材每周排期」(?sheet=nPw5Dc)（只读），这个角度在表里就写那一行的日期。读不到就都不写 sched，页面会显示「还没排」，最后回复里说一句。
- 和前一天比，use case 和角度都没变时可以沿用，但 shot 和 sched 要更新。
- 写法：方向不写太死，唯西可以在 use case 范围内发挥。不写产品短板和产品提升，不写投放参数和预算，不写连续 3 留，不写「重排」「直接加量」「不要再加」。素材名照抄原名，use case 带名字。不用破折号。

## 排期看板（每天）

Reina 11/4 定：「本周素材排期」放进素材看板，从 11/4 起按天归档可回溯。页面在 schedule/<T>/，schedule/ 是最新一天，schedules.json 是目录。日报、周报导航里的「素材排期」链到这里。T = 今天（看板当天），D = 昨天（数据日）。「投放数据_分日」更新到 D 之后跑。

1. 读 `'投放数据_分日'!A1:AB`（日报读过就复用）和 `'素材映射'!A1:J`（J 列是「子方向（PS03）」），get_values 结果存成文件。
2. `python3 tools/schedule_data.py --sheet <分日文件> --map <素材映射文件> --date D --out-dir /tmp/sched`。输出 `NO_DATA`：表里还没有 D，等 20 分钟再读。有 WARNING（PS03 没标子方向）写进最后回复。
3. 进度核对（要用 Reina 电脑上的内置浏览器，只读，不改飞书）。下面 6 个 tab 每个都 navigate 到带 `?sheet=` 的网址（切 tab 只能靠 URL），用 javascript_tool 跑 tools/schedule_read.js 全文，返回值原样存成 /tmp/sched/feishu/<tab id>.json：
   - A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：kMJdAv 扩量素材迭代排期、f18d7b 脚本及成片、nPw5Dc 新素材每周排期
   - B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：c665d9 脚本&成片、EnYgPG 真人素材和ai切片二剪、3KtioB 扩量素材迭代排期（是空的也存，能正常跑）
   然后 `python3 tools/schedule_progress.py --dir /tmp/sched/feishu --date T --out /tmp/sched/progress.json`。某组的 tab 没读全，这组不进页面，missing 里写着，最后回复里说哪组没核对。
4. `python3 tools/schedule_build.py --data-dir /tmp/sched --date T --progress /tmp/sched/progress.json`：写 schedule/T/index.html、schedule/index.html，更新 schedules.json。电脑连不上就不加 --progress（页面没有进度那一行），其余照出，最后回复里说今天没核对。输出的 WARNING 都写进最后回复。
5. 提交 schedule/、schedules.json（改过 plan 也提交 tools/schedule_plan.json），push 到 main。

落下了怎么办：progress.json 的 groups.A.lag、groups.B.lag 是落下的行（行号、use case、差几条）。只推给 Reina，把 draft.A、draft.B 附上，这是可以直接发给唯西两个素材群的提醒草稿，发不发、怎么改她定。不自己发群，不改飞书，草稿不带看板链接。

schedule_read.js 只返回算进度要的字段和最近 10 天的行，脚本及成片按 use case 和完成时间合起来（11/2 起 A 组这张表的 UC_ID 列没填，从素材命名或成片文件名里取 UC）。11/4 在 6 个 tab 上真跑过。

排期内容只在 tools/schedule_plan.json，页面不手改：
- E 是排期条目：d 交付日、g 组、t 类型、n 条数、s 状态（done 已交没花钱、todo 待交、cut 建议拿掉、add 建议加）、src 和 link 是飞书位置、to 是拿掉后怎么办。已上线的条数从数据算，不写在这里。
- Reina 确认调整、写进飞书之后，把对应条目改掉（add 改 todo，cut 删掉或换 uc），MOVES 也跟着改，asof 改成当天。
- 表里写了「先不拍」「顺延」（开头的【】或脚本备注）的行不算该交。B 组二创那张表没有备注列，这种行写进 plan 的 skip_rows。
- 每周一换新一周：week、asof、sub、meters（已排 / 本周产能）、E、MOVES、MT、GROUPS 都要更新。week 和 T 所在那周对不上时，页面不显示产能条、结论和要改什么，脚本打 WARNING。
- schedule/2026-11-04/ 是 11/4 手工定稿版（schedule-source=manual），不覆盖，也不重算。

页面日期都按 D 和 T 算：柱子是 D 往前 14 天，排期列是 T 到 T+4。过了日子的 todo、cut、add 不再算进后面的供给，看进度那一行；已交没花钱的挪到今天，asof 之后上线的条数扣掉。

口径（schedule_data.py）：
- 批次日期 = 第一次上传巨量（素材ID >> 32 是秒，加 8 小时）。同名的推送版、修改版（前缀 推送视频_，后缀 _合规修改、修改版、_改动、 (1)）和同一脚本编号（如 A18-06-cw-20261023）算同一条，取最早。
- 条数只算花过钱的。c7 = D-6 到 D 的消耗；次留率、次留成本看 D-6 到 D-1。
- PS03 表里一行，三部分按素材映射 J 列分，写在执行细节。还是库外、靠 FUZZY 归 PS03 的算消息排清单。
- 单条跑量：首花 D-7 到 D-2 的素材（不早于 STABLE = 10/29：10/28 那批赶上预算放开，后面的批次到不了），前 3 天消耗按全盘一天 ¥15 万折算后的条均。sh 是近 7 天消耗占比，np 是 D-14 到 D-1 上传的条数占比。放量 = 单日 ≥ ¥2,000。
- 预计下降额：第 2 天以上、最近 2 天日均 ≥ ¥100、峰值在最近 2 天、第一次单日 ≥ ¥200 在 D-5 之后的素材，最近 2 天日均 × 50%（DROP），算在首花 + 4 天，早于 T 的算 T。第 0–1 天的新素材不算下降，算进预警的「到的条数」（n01）。回测 10/22–11/1：第 4 天日均 ≥ ¥1,000 的素材除全盘后还剩 40%，全部素材还剩 46%；第 0–1 天日均 ≥ ¥100 的后 3 天 1.2 倍。
- 预警（schedule_data.py 的 flow）：页面只显示红色警告，不显示金额。这天预计掉的比补的多，差额超过 ¥500 和现在消耗的 10%（全盘 5%），现在消耗不到 ¥1,000 的不标。补的按 CURVE 算，AI 和二创分开，每条每天取这个方向这类素材前 3 天日均，不足 5 条用这类素材全盘的。前两天刚上的素材按实际跑量校正。待交的按交付第二天首花。
- 回收（schedule_data.py 的 recover）：前 3 天（D-3 到 D-1）放出的素材，按方向和 AI、二创分行，3 条以上才列。跑起来 = 首花第 0–1 天有一天按 ¥15 万折算花到 ¥200。预期 = 这个方向这类素材之前跑起来的比例 × 条数。5 条以上且碰巧概率 <10% 才标不及预期、超预期。可能见顶 = 不及预期 + 最近 3 天占比没涨 + 7 天内上了 10 条以上。
- 要看片的素材（recover 的 bad）：首花 7 天内，激活 ≥100，次留比同样这些天的全盘低 5 个点以上，配底稿。Reina 11/5 定：use case 的性质不因一批素材改，新素材差要下钻内容，不打在 use case 上。下钻顺序见项目文档 claude/new-batch-retention-drill-1105.md。
- 批次回收（schedule_data.py 的 batches）：每个上传日几条、几条跑起来、第二天花多少。柱子下面的条数按它标色，过半绿色，不到四分之一红色，3 条以上才标；页面顶部一行写前天上传这批第二天每条花多少。
- 在跑：当天花了钱的条数，按批次分，悬停柱子看。
- 分档（schedule_data.py 的 tier_stats，schedule_build.py 的 tier_view）：线写在 schedule_build.py 的 UP_*、IN_*，定义见 claude/usecase-tiers-1104.md。只显示，不自动移档：探索过线标「可升」，跑量少 + 留存好过升级线也标「可升」。移档要 Reina 定，改 schedule_plan.json 的 GROUPS，并在 MOVED 写从哪档来、哪天，7 天内名字旁标「新进」。
- 条数建议只看能不能跑量，不看留存。阈值在 schedule_build.py 的 rule_rows，和 11/4 定的一样，先跑 1–2 周。schedule_build 输出的 all 是全盘预警的天，red 是 {use case: 预警的天}。

## 周报（每周一，Reina 11/1 定）

页面和 notes 不写 T1、T2、T3 这些代号（Reina 11/2 定），写大白话：能放量、留存好；量中等、留存好；能放量、留存不达标；量小，先观察。头部素材表不放脚本，脚本和分析放第六部分。
页面是给公司看的报告：不写电脑没连上、几条没读脚本、脚本 bug、口径修正这类过程信息，这些只放推送和最后回复。页面和 notes 不只写 use case 编号，要写名字。「继续扩量的 use case」和二创素材的标签写全：一级分类 + UC_ID + 中文简称（页面按 uc、tag 字段自动带出）。

M = 上周一。数据要等「投放数据_分日」更新到周日（周一 07:40 前）。

1. 读 `'投放数据_分日'!A1:AB`（存成文件），再读 `'✅ Use case 库'!A1:G200` 跑 `python3 tools/sync_ucs.py <库文件>` 同步简称，然后 `python3 tools/week.py --sheet <分日文件> --week M --out /tmp/week.json`。输出 `NO_DATA` 就是周日还没出。
2. 读全片脚本（见下面「读全片脚本」）：`python3 tools/script_todo.py --week /tmp/week.json --out /tmp/sc`，范围是周消耗 ≥ ¥2,000 的所有素材，脚本库里没有的都要读。
3. 看 /tmp/week.json 和 scripts/ 写 `notes/week-M.json`：
```
{"headline": "一句话结论",
 "insight": [{"t": "结论", "d": "证据（可用 <b>）"}],                       // 核心 insight 3 到 5 条
 "scale":  [{"uc": "WK05", "t": "动作", "d": "依据和下周具体怎么加"}],      // 继续扩量的 use case：T1 和差一点进 T1、T2 里留存好的，2 到 4 个
 "drop":   [{"uc": "SH02", "t": "动作", "d": "依据"}],                        // 留存差的 use case（页面只写「差」，不写「不要再加」，公司战略可能还要继续试）：能放量但留存不达标里最差的、量小且留不住的、Use case 库里已暂停还在花钱的，3 到 6 个，同时显示在第三部分表里的「留存差」
 "remix":  [{"id": "素材ID", "tag": "UC_ID", "t": "素材简称（类型）", "d": "数据", "how": "为什么好、二创怎么做"}],  // 拿去二创的，从 top 里挑 2 到 4 条，优先 pick=true
 "stop":   [{"t": "动作", "d": "依据"}],                                    // 停掉或降预算，2 到 4 条，优先 bad 里多花的钱最多的
 "other":  [{"t": "动作", "d": "依据"}],                                    // 产能、口径、要谁跟进，1 到 3 条
 "angles": [...],                                                            // 扩量角度建议，每周都要写，格式见上面「扩量角度建议」
 "uc": {"UC_ID": "这个 use case 下周做什么"},                               // 表里 T1、T2、T3 每个一句
 "l1": {"一级分类": "这个分类下周做什么，一句"},                          // 第二部分「一级分类」，周消耗占比 ≥ 0.5% 的每个写一句
 "wk_market": [{"t": "结论", "d": "依据，要和上周周末比"}], "wk_top": [{"t": "结论", "d": "依据和下周怎么试"}], "wk_names": {"素材ID": "头部素材短名"},  // 第一部分「周中和周末」，分大盘和头部素材，先写结论再写依据，小标题必须是一句结论，不能只写一个词；先按上线天数拆（wk.age）、看同一批素材过周末（wk.carry、wk.batch），再下分类结论，新老素材混着看会把新素材的跌算到分类头上；周五激活的人周六回访，周五也算周末；上周周中被单日拉低要说明，不能只比均值；说放量造成要有同批素材加量才跌的证据；每个一级分类写清老素材和新素材各自怎么变，标签用老素材好、新素材跌、新老都跌、两条拉高、样本小（四个字以内）；老素材好要先去掉最大的一两条再看；"wk_tags": {"一级分类或素材ID": "周末多投/周末压/看不出/样本小"}
 "rules_note": "规律的依据范围一句",
 "rules": [{"t": "规律 + 下周怎么做", "d": "依据：每组多少条、次留率、次留成本、连续 3 留，少于 5 条的只说方向"}],  // 第六部分「头部和拖后腿素材的规律」，3 到 6 条，不摆脚本
 "output": {"note": "各类型按什么日期算", "rows": [{"t": "类型", "n": 产出, "plan": 计划, "live": 上线投放}]},  // 素材产出数量，放第五部分。小红书、抖音从「Today KOL/KOC 视频」按发布日期数；AI、唯西星图达人、自建号、星广按唯西表和素材产出日报；二创和上线投放从「投放数据_分日」按首次消耗数；计划按素材产出日报，二创计划按「每周素材追踪」
 "top_use": {"素材ID": "十来个字：继续投、小量试、修好再扩；第四部分 heads 全部列出，标签和日报、use case 的说法一致：能放量 + 次留好、能放量 + 成本略高、能放量 + 次留一般、能放量 + 次留差、能放量 + 次留好但贵、激活太少，不写好、不好、一般这种词；能放量 + 次留好的每条写，其余没写的页面自动写原因"}}               // top 里没进 remix 的每条，放在头部素材表
```
4. `python3 tools/build_week.py /tmp/week.json`：写 week/M/index.html、week/index.html（最新一周）、weeks.json。
5. 提交 week/、weeks.json、notes/week-M.json，push。

口径：消耗看整周；次留看周一到周六激活（周日的次留下周才出）；连续 3 留看周一到周四激活。门槛在 week.py 的 WTH：能放量的 use case = 周消耗 ≥ 全盘 3% 且 ≥ ¥20,000；头部素材 = 这周有一天消耗 ≥ ¥2,000 或周消耗过全盘 1%，全部列出打标签（Reina 11/4 定），次留好 = 激活 ≥ 100、次留率不低于全盘、次留成本不高于全盘；拖后腿 = 周消耗 ≥ 全盘 1%（最少 ¥5,000）但次留率 < 全盘 85% 或次留成本 > 1.2 倍，按多花的钱排，最多 8 条。pick = 次留率高全盘 5% 以上、次留成本低 10% 以上（连续 3 留不进这条规则）。

## 读全片脚本（日报、周报都要做，Reina 11/1 定）

每条投放素材读一次全片字幕，存成 scripts/<素材ID>.json（格式见 tools/scripts_lib.py），以后日报、周报都直接用。日报、周报的素材表都不放脚本（Reina 11/2 定），脚本只用在后面的分析里：notes 里引用开头原话和结构，compute.py 和 week.py 按 Today 第几秒出现、开头怎么钩、形式、时长分组算次留（patterns，页面「脚本规律」）。

- 要读哪些：日报 `python3 tools/script_todo.py --daily /tmp/results.json --out /tmp/sc`（「四、昨天消耗排行」全部、拖后腿和次留好但贵的、扩量和它们的原素材）；周报 `--week /tmp/week.json`（周消耗 ≥ ¥2,000 的全部）。已经读过的不重读。写 /tmp/sc/todo.json 和 /tmp/sc/jl.js。
- 必须用 Reina 电脑上的内置浏览器读，不读不写分析。todo 超过 12 条就拆成 2 到 4 批，用 Agent 工具并行跑，每个 agent 用自己开的 tab（tabs_create，第一个没面板就 preview_start），只写 scripts/ 下自己那批的文件。
- 每个 tab：navigate 到巨量素材页 https://ad.oceanengine.com/material_center/management/video?aadvid=1878223927194825 （网址里有 login 就停，不输入账号密码）；resize_window 1000x2000；跑这一批的 jl.js（`python3 tools/script_todo.py ... --out` 生成后可以按批拆：同一段 JS 只换 NEED 列表），`await __jlWait()` 到 done；再跑 tools/frames.js 全文。
- 每条：先 `__v.start('thumbs', 链接, [0.5,3,6,10,15,20,30,40,50], '标签')` 看整画面（字幕在多高、形式、Today 第几秒出现）；再 `__v.start('script', 链接, '标签', step, y0, y1, 3)` 读全片字幕，y0、y1 按字幕高度取，字幕一秒一换的 step 用 1；截图只有约 750 像素高，画布更高就 `__v.page(1)`、`__v.page(2)` 每次下翻 700 像素再截。链接用 `__jl.res[ID].u`，没有就用 todo.json 的 video_permanent。
- note 里写看到的问题：字幕打码、「审核」「DEMO」「样片」或平台水印（第几秒）、Today 界面露出 bug 或内部字样、App 名不是 Today、隐私露出、素材名和内容对不上、活动口径（永久免费、送 Token、Pro 权益）。
- 做完 resize_window preset desktop，关掉自己的 tab。
