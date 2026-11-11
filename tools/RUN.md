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
   - 回补当天次留（Reina 11/11）：build 完再跑 `python3 tools/rt_backfill.py --sheet <分日文件> --date <D-1>` 和 `--date <D-2>`，把前两天日报「四、昨天消耗排行」的当天次留率、当天次留成本补上（X 天激活的人的次留 X+1 才回传完，T = X+2 才看得到；D-2 再补一次是因为次留第二天还会小涨一点，比如 11/8 的全盘从 29.3% 涨到 31.0%）。写 notes/rtday-X.json 并重画 X/index.html，和页面一起提交。D 当天的这两列先显示「待回补」。11/4 到 11/9 已回补。
6. 提交 D/、index.html、reports.json、tools/links.json、tools/gaifa.json、notes/（和改过的 tools/ucs.json），push 到 main。

已经发布的日子只补链接、不重算：`python3 tools/relink.py YYYY-MM-DD [--sheet <分日文件>]`（带 --sheet 会补素材类型）。

口径：消耗看 D；次留率、次留成本看 D-3 到 D-1 激活的人（巨量次留记在回访那天）；连续 3 留率、成本看 D-5 到 D-3 激活的人（AB 列「3日留存」按激活日记，约 3 天才稳，10/16 起有数）；标签和分层只看次留。四、昨天消耗排行只列昨天消耗 ¥300 以上的素材（TH 的 rank，Reina 11/11 从 ¥1,000 降到 ¥500 再降到 ¥300，11/4 到 11/10 的页面已回补）。门槛在 compute.py 的 TH。

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

LG02 拆分（Reina 11/5 定）：按有没有一个要拿到的结果分。LG02 备考和转行：备考、考证、转行，要考过什么、转成什么说得出来（雅思、考研、CPA、商务英语、外企英文面试、岗位要求会用 AI 都算）。LG03 学语言和新技能：没有硬结果，日常口语、吉他、剪辑这类。给孩子选课归 PS02。素材映射按字幕标：C 列有值时 C 优先，未标、待对应才看 I。已按字幕归好：LG02-07 法考、LG02-09 转行、「又错」留 LG02；LG02-02、LG02-10 归 LG03；LG02-08 选编程课归 PS02；碎片读书归 LG01。10/27 到 11/4 的日报页面和 notes 11/5 已按新分类重算（Reina 要求），周报 week/2026-10-26 不改（Reina 11/5 同意），留作当时的记录，page 和 notes 还是旧口径、旧分类，下一份周报起用新口径和新分类。每周追踪第三块（Z:AQ）已有的 10/19、10/26 两周不加 LG03 行，这两周 LG03 的消耗不算进第三块的 UC 行；从下一个新周块起，学习与成长下加 LG03 行。

## 判差第几天（Reina 11/4 定，日报第四节和第五节）

compute.py 的 bad_streak 自动算，每条素材写进 bad_n、bad_first、bad_after、bad_up，不用手填。
- 时间：D 激活的人 D+1 才有次留，表 D+2 上午才看得到。所以 x 这天上午看的是 x-4 到 x-2 激活的人，第 1 天从看得到那天上午算，不追之前花的钱。
- 判差：这 3 天激活合计至少 50 人，且次留率低于同期全盘的 80%，或次留成本高于同期全盘的 1.25 倍。和同期全盘比，周末已经扣掉。门槛在 compute.py 的 TH（judge_act、low、high、stuck_n、stuck_cost）。
- 第四节「判差」列写连续第几天。第五节「判差 3 天以上还在花」列连续 3 天及以上、昨天还花 ¥200 以上的；D 的消耗比第一次判差那天高 50% 以上且至少 ¥500，标「判差后放量」。
- 表里只有消耗，没有开关状态：掉量可能是关了，也可能是系统不跑了。没读过巨量投放状态前，不写「代理没关」。

## 五、昨天上新的素材（Reina 11/9 定，按上传算）

两种日期都要在页面上标清楚（Reina 11/9）：「上新」「上传」只指上传到巨量的日期，只用在五；「首次消耗」指投放表第一天有消耗，四的新上线和绿底、七、八的批次、开头那段话、周报的「本周首次消耗」「上线投放」都按首次消耗。写 notes 时也照这个分：说上传就写上传，说开始花钱就写首次消耗，不写含糊的「上线」「新上」。

上新 = D 上传到巨量的全部素材，团队要看 制作 -> 上传 -> 消耗。上传时间取素材ID 里带的时间（ID 右移 32 位是 unix 秒，北京时间），制作 = 素材名最后的日期，第一次消耗 = 投放表第一天有消耗。之前上传、D 才第一次花钱的只在汇总里按上传日数条数和消耗。
- 没花钱的素材投放表里没有，要从巨量素材库补：在第 2 步之前跑 `python3 tools/up_js.py --date D --out /tmp/linkjs`，在巨量素材页（同 jl.js 的页面，网址里有 login 就停）用 javascript_tool 跑 up.js 全文，返回的 JSON 原样存成 notes/uploads-D.json（字段 date、hubs、n、items：{素材ID: [名字, is_cost]}；存的时候可以只留 items 的名字），和页面一起提交。compute.py 默认读 notes/uploads-D.json，没有就只列有消耗的，页面上会写「今天没读到巨量素材库」。电脑连不上就跳过，最后回复里说一句。
- 每条都要有能打开的链接：links_js.py、jl_js.py、relink.py 都把 newd 算进要找链接的素材（没花钱的也算）；唯西日报当天通常还没有这批，靠巨量直取（jl.js）补视频，KOC/KOL 再用原片表补原帖。「推送视频_X」巨量里找不到时，compute.py 用同名成片 X（去掉日期）的视频。build.py 输出「五、昨天上新的素材有 N 条没有链接」时要补完再提交，补不到的写进最后回复。
- 只读：up.js 只调素材列表接口，不点按钮。
- 投放账户数和账户跑起来率（Reina 11/9：放日报第五节，不放专题）：在第 2 步之前跑 `python3 tools/acct_js.py --date D --out /tmp/linkjs`，打开 https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746（巨量升级版工作台，跳到登录页就停，不输账号密码），用 javascript_tool 跑 acct.js 全文（返回 started），再反复跑 `await __acctWait()` 到 st 是 done；把返回值原样存成 /tmp/linkjs/acct_wait.json，再依次跑 `__acctGet(0)`、`__acctGet(1)`……每次返回值原样存成 /tmp/linkjs/acct_k.json，直到 d 是空字符串；然后 `python3 tools/acct_save.py --date D --wait /tmp/linkjs/acct_wait.json /tmp/linkjs/acct_*.json` 存成 notes/acct-D.json，和页面一起提交。compute.py 默认读这个文件，没有就第五节的投放账户数显示「—」、最近 10 个上传日那张表不出。只调查询接口，不点任何按钮，不点「体验智擎版」。err 里有「只拿到」说明分页没拿全，写进最后回复。
- 集中度（Reina 11/11，日报「四、昨天消耗排行」的单项目最高消耗、头部占比两列，按项目不按账户）：按 tools/conc_js.py 文件头的三步跑。第 1 步在同一个工作台页面跑 `python3 tools/conc_js.py --date D --out /tmp/linkjs` 生成的 conc.js（拿 D 当天素材 × 账户），返回值存成 /tmp/linkjs/conc.json；第 2 步 `python3 tools/conc_js.py --date D --out /tmp/linkjs --ebp /tmp/linkjs/conc.json` 生成 conc_proj.js，在 https://ad.oceanengine.com/ad/web/std/manage?aadvid=1879654096082505（智擎版投放管理，只看不点，不点开关、编辑）跑，`__concWait()` 到 done，err 不空跑 `__concRedo()`，再 `__concGet(k)` 存成 /tmp/linkjs/concp_k.json；第 3 步 `python3 tools/conc_save.py --date D /tmp/linkjs/conc.json /tmp/linkjs/concp_*.json` 写 notes/conc-D.json，和页面一起提交。都从会话记录里解析工具结果写文件，不手抄。compute.py 默认读它，没有就两列显示「—」。单项目最高过 ¥1,000 标绿（优先加产）；D 花 ¥1,000 以上但单项目不到 ¥500 标红（分散）。warn 里有查不到项目的账户写进最后回复。11/9、11/10 已回补。
- 口径：投放账户数 = 该素材有展示的账户数（同一账户多个项目算一个，是被建次数的下限）；账户跑起来 = 在该账户第一次有展示后 3 天内花到 ¥100；账户跑起来率 = 跑起来的账户 ÷ 投放账户，只算上传满 3 天的批次。
- 冷启率（Reina 11/11，朱艺涛提的牵引指标）：compute.py 自动算，在第六节「冷启动率」。窗口 = 上传当天 + 第二天（CSW = 2，Reina 11/11 从 4 天改成 2 天，第二天就能看；按上传日算，不按首次消耗）；过冷启 = 窗口激活 ≥ 这批自己的门槛：上传日前 8 天到前 2 天（共 7 个上传日，Reina 11/11 从 30 天改成 7 天）上传、花过钱的素材同一窗口激活的 80 分位（每批各算各的）；另有「去掉预算影响」一列，门槛 = 那批基准素材窗口激活占同期全盘激活比例的 80 分位 × 这批窗口里全盘激活。分母 = 当天上传全部素材（notes/uploads-日期.json ∪ 有消耗 ∪ 有展示）。窗口没过完的批次（只有 D 当天上传的）显示「目前 x%」。颜色：比这几批合起来高、低 3 个点以上才标。uploads-D.json 每天都要存，不然那天分母只剩有展示的。
- 冷启的项目数据（Reina 11/11，每天做）：按 tools/proj_js.py 文件头的三步跑（账户取集中度第 1 步的 conc.json，在智擎投放管理页跑 proj.js，__pjGet 分段存 proj_k.json，proj_save.py 写 notes/proj-D.json）。compute.py 读到就在冷启共性问题里写「新建、没有高热老素材的项目有多少没起量（到 D 花不到 ¥100）、每个项目塞了多少素材、几条素材占 80% 花费」，每天面板里写「装没拿到量素材的项目有多少没起量」。Reina 11/11 定：不再写「钱被之前上传的素材拿走」，那是全盘口径，项目里新素材基本不和高热老素材同项目。
- 之后依次是六、冷启动率（最近 10 个上传日，Reina 11/11 单独成一节），七、拖后腿，八、批次，九、核心 insight。

## 九、核心 insight 和下一步（Reina 10/31 定，日报口径，不排每周产能）

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
 "uc": {"UC_ID": "这个 use case 下一步具体做什么"}}
```
写法：日报口径，不排每周产能，动作按小步快跑写（今天停、明天加两三条、等次留再定）。每条都要有数。delta 和 steady 要拿前几天的数比：用同样参数跑 compute.py --date D-1、D-2 到别的文件（只读取，不发布）。样本小的（激活不到 50）直说样本小，不当结论。sharp、短，不写套话。全程中文，不用破折号。

## 唯西自建号（Reina 11/9 定，日报周报都单独算）

唯西自建号的视频不走普通投放，自动推进巨量星广任务「Today-唯西星广」（任务 ID 7702316618969333810，升级版工作台 → 素材 → 星广联投 → 任务管理），所以分日表里「来源」会写星广。唯西进度表「自建号脚本与成片」(?sheet=UJsWF1) 的「素材ID」就是星广任务里的巨量素材ID，不是抖音作品 ID。
- 名单在 tools/zijianhao.json：accounts 是自建号的抖音号（11/9：蓝莓🫐脑袋 31236614672，女号朵拉、潇潇；今天用点AI 54164114746，男号，按标题和表里男号成片对上，唯西还没确认），ids 是这些号在星广任务里的视频。compute.py、week.py 的 kind_of 按 ids 把它们算成素材类型「唯西自建号」（不再算星广），日报「素材类型」表和周报第五部分一直有这一行，没花钱时写「还没消耗」。
- 每天补名单（日报在巨量那一步顺手做）：内置浏览器打开星广任务管理，点「查看详情」，跑 tools/zjh_read.js，结果存 /tmp/zjh.json，再 `python3 tools/zjh_merge.py /tmp/zjh.json`。输出的 other_accounts 里出现新的、像自建号的号（唯西说的、标题都是「…？today帮你 #todayai」这种），不自己加进 accounts，写进最后回复让 Reina 确认。只读，不点停投广告、下载、编辑、视频确认。
- 周报第五部分 output 的「唯西自建号」上线投放 = /tmp/week.json 的 kind 里「唯西自建号」这一行的 n_new（这周第一次有消耗的条数）。11/9 时整个星广任务累计只花了 ¥0.16，自建号 0。

## 扩量角度建议（Reina 11/9 先去掉）

日报和周报都不写 notes 的 angles，页面也不再显示这一块（模板和 10/27 以来的往期页面 11/9 已删）。以前的写法（11/3 定）在 git 历史里，Reina 说恢复再加回来。

## 排期看板（每天）

Reina 11/4 定：「本周素材排期」放进素材看板，从 11/4 起按天归档可回溯。页面在 schedule/<T>/，schedule/ 是最新一天，schedules.json 是目录。日报、周报导航里的「素材排期」链到这里。T = 今天（看板当天），D = 昨天（数据日）。「投放数据_分日」更新到 D 之后跑。

1. 读 `'投放数据_分日'!A1:AB`（日报读过就复用）和 `'素材映射'!A1:J`（J 列是「子方向（PS03）」），get_values 结果存成文件。
2. `python3 tools/schedule_data.py --sheet <分日文件> --map <素材映射文件> --date D --out-dir /tmp/sched`。输出 `NO_DATA`：表里还没有 D，等 20 分钟再读。有 WARNING（PS03 没标子方向）写进最后回复。
   补链接：点柱子面板里素材名链到这条投出去的视频，不用博主原帖（原帖在后面单独写「原帖」）。schedule_data 跑完后，`python3 tools/links_js.py /tmp/results.json --out /tmp/linkjs --roi /tmp/sched/roi.json`，在内置浏览器跑 yulan.js，存成 yulan.json，再跑 `python3 tools/links_merge.py /tmp/linkjs`，然后才跑 schedule_build。唯西日报只覆盖一部分，最近几批经常没有（11/6：11/4 那批 79 条全没有），所以再跑巨量直取：取这些窗口里还没有 video 的素材，用 jl.js 同样的 NEED 在巨量素材页跑，存成 /tmp/linkjs/jl.json 再 links_merge（巨量链接约 2 天过期，每天都要刷新）。扩量之外，星广素材巨量库里常找不到，没有就不带链接。这一步改出来的 tools/links.json 是临时的，schedule_build 之后 git checkout -- tools/links.json，不提交。连不上浏览器就跳过，还没有视频的素材名不带链接。
3. 进度核对（要用 Reina 电脑上的内置浏览器，只读，不改飞书）。下面 6 个 tab 每个都 navigate 到带 `?sheet=` 的网址（切 tab 只能靠 URL），用 javascript_tool 跑 tools/schedule_read.js 全文，返回值原样存成 /tmp/sched/feishu/<tab id>.json：
   - A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：kMJdAv 扩量素材迭代排期、f18d7b 脚本及成片、nPw5Dc 新素材每周排期
   - B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：c665d9 脚本&成片、EnYgPG 真人素材和ai切片二剪、3KtioB 扩量素材迭代排期（是空的也存，能正常跑）
   然后 `python3 tools/schedule_progress.py --dir /tmp/sched/feishu --date T --out /tmp/sched/progress.json`。某组的 tab 没读全，这组不进页面，missing 里写着，最后回复里说哪组没核对。
   分日表审核核对（Reina 11/5）：`python3 tools/review_cover.py --sheet <分日文件> --date D --dir /tmp/sched/feishu --out /tmp/sched/review_cover.json`。用 schedule_read.js 返回的 cov，查 11/5 起首花的扩量、二剪有没有都审过：no_table 没传表就投了，not_reviewed 传了没审就投了（含他们自己标通过、没有审核备注的），need_fix 要改还在投。第一行 line 进推送，名单写进 claude/schedule-progress-MMDD.md。只告诉 Reina，不发群，不改飞书。11/5 用 11/3、11/4 的数据试跑过：扩量都对得上，没传表的 27 条全是 A 组新原片首剪（today koc_UC_博主_二创_精剪_剪辑），11/5 23:39 已在 Today素材群告诉单志远、赵勇洲，以后这类也传到扩量排期，对应行或最下面加一行。
4. `python3 tools/schedule_build.py --data-dir /tmp/sched --date T --progress /tmp/sched/progress.json`：写 schedule/T/index.html、schedule/index.html，更新 schedules.json。电脑连不上就不加 --progress（页面没有进度那一行），其余照出，最后回复里说今天没核对。输出的 WARNING 都写进最后回复。
5. 提交 schedule/、schedules.json、notes/schedule-T.json、scripts/（改过 plan 也提交 tools/schedule_plan.json），push 到 main。

改排期（Reina 11/5 定）：今天之后的排期，确定要改就直接在原来的行上改，把这一行的 UC、原素材、条数、怎么改都换成新的，不加「调整」标记、不写改了什么、不留旧内容，也不用通知唯西。改之前先看「扩量素材名」有没有已交，已交的不动。今天的行不改。

产量口径（Reina 11/10 晚定）：A 组一周 AI 100 条、真人二创 100 条（11/10 晚改，冲一下）；B 组一周 150 条，AI 和真人二创都算在里面；按周一到周五每天约 30 条排，周末不排；每天至少 20 条是头部模板变式（含同脚本换画面）。只换前贴（只换开头 hook 那几秒画面、后面照旧）的版本不算进 150 条，也不算变式，素材名里写「换前贴」，schedule_read.js 数扩量素材名时去掉这些。plan 的 meters 按这个写：A 组 AI 100、二创 100；B 组 AI 产能 = 150 − 这周排的二创。
产能改了（Reina 11/11 晚）：B 组每周只能做 120 条（AI 和二创合计，每天约 24 条），A 组真人二创每周 75 条（每天约 15 条），A 组 AI 还是 100 条。排期按一周总数卡：这周已经排了的天不动，从第二天起把剩下的天压到周总数以内，先顺延没依据的二创冲量和不是头部模板的行，头部模板变式和新赢家留着。meters 按这个写：A 组 AI 100、二创 75；B 组 AI 产能 = 120 − 这周排的二创；week_total A 175、B 120。素材产出看板目标跟着变。

变式按模板集中（Reina 11/10 晚）：头部模板变式不要一个模板拆成一天一两条，一天围绕同一个模板做完几条（每组每天尽量 4–6 条一个模板，同一套结构和录屏流程，换人设和场景一起拍），排期表一行就是「某模板这天做 n 条」，怎么改里列 n 个角度。素材产出看板顶上看总数（11/11 起 A 组一周 175、B 组 120），变式占比是第二层。

头部模板变式（Reina 11/10 定）：「头部素材结构提取和变式（11/9）」表（https://my.feishu.cn/sheets/VEBUs3HTjh3dHqtojlsckJzmnqS）22 个模板的变式角度 A、B 两组都排，同一个角度两组各做一版；每个模板最多 3 条「同脚本换画面」（台词照原片逐句用，只换人设、场景、画面），素材名必须带「同脚本换画面」；每天 AI 素材至少 2/3 是变式（每天 30 条里至少 20 条），全周至少 70%，剩下的留给唯西自己发挥（表里 UC_ID 写「自选」的行，进度不算）。11/10 排了 11/11–11/15：A 组第 194–246 行、B 组第 83–124 行；这周没排完的（另一组那一版、其余同脚本换画面、PS01 角度 6）下周接着排，清单在项目文档 claude/variant-schedule-1110.md。

排期规则（Reina 11/5 定）：同一条原片不限条数，也不限只换开头。全片重配主要看台词怎么写，切片可以随便取用。台词要具体，底稿的数字、金额、省的时间尽量留着。新原片从「Today AI KOC KOL 真人原素材」表找没剪过的，按原则文档附录 B 可以重写台词、全片重配、精简，最长 65 秒左右。换人设、换场景时要写明录屏跟着换。

所有分析早上 10 点前做完（Reina 11/5 定）。建议只动 T+1 起的排期，当天的排期不改，除非 Reina 明确说要改。

内容下钻（第 4 步之前做，Reina 11/5 定）：每天都看前天首花那批的具体内容。第二天没跑起来的（红）分析为什么，跑起来的（绿）分析好在哪。只看数不算分析。
- `python3 tools/schedule_why.py --sheet <分日文件> --map <素材映射文件> --date D --out /tmp/sched/why`：context.json 是红、绿的方向（这批 3 条以上）和每条素材：是不是扩量、根素材之前上过多少条花过多少、这个方向最近跑起来的素材；todo.json 和 jl.js 是还没有脚本的素材，最多 20 条。
- 按下面「读全片脚本」读 todo 里的素材，存进 scripts/。超过 12 条拆批用 Agent 并行。电脑连不上就只写数据能看出来的，并写明没看片。
- 看操作，每天都要看，不只看内容。两件事：
  - 读「Today-唯西 巨量投放1群」（1 组，金铭、陈妍）和「Today-唯西2组 巨量投放对接」（2 组，熊斌、吕阳）D 和今天早上的消息，只读不发。打开 https://yqeu8jvi0p.feishu.cn/next/messenger/ ，用真实点击点开 [data-feed-id] 对应的行（JS click 点不开），`[...document.querySelectorAll('.message-item')].filter(m=>!m.parentElement.closest('.message-item'))` 读消息，往上滚动时按 m.id 去重，长消息要带上全文。m.id 右移 32 位是秒级时间戳。记下：按次留关了什么线、点名控了哪些类型（learning、family、health 这些）、基建增减、新项目新批次有没有被卡。
  - 用 tools/schedule_acct.js 扫 D 和 D-1 按账户的消耗：这批钱在哪几个户（前 3 户占比）、哪一组投手、老素材掉的钱集中在哪些户。钱集中在 1、2 个户的，几条一起跑起来不算几个独立信号。
  - 判断时分开写：新批为什么没放起来（内容、首日次留）；老素材为什么掉（投手砍量还是自己掉）。同一组账户同一天，其他块放大而这块没放大，才说块之间的差不是操作。
- 同一条原片第几条不当原因（Reina 11/5）：10/14 起的二创，第 4 到 6 条 31% 跑起来，第 11 到 20 条 26%，和前 3 条差不多；10/27 第 13 条的全片重配是最大的几条；10/29 到 11/2 前 3 条也只有 9%。同批同原片第二天能差上百倍，先比台词。context.json 的 root_before 只当背景。
- 对比读：这条和它的根素材、和这个方向最近跑起来的素材，比开头第一句、讲的痛点、形式、Today 第几秒出现、演示的是哪一下、结尾落在哪。写看到的事实，原因是判断就写成判断，不把一批素材的结果算到 use case 头上。
- 写 notes/batches.json（一直累积，不按天分文件，只加这一天的键，不动旧的）：键是「UC|MM-DD」（UC 是看板那一行的 id，PS03 三部分合成一个键，MM-DD 是首花日），3 条以上的批次每批一条：`{"verdict":"内容 / 操作 / 都有 / 看不出 / 好在内容 / 好在操作","why":"一句话依据","good":"跑得好的素材是什么、好在哪，素材名照抄，带开头原话","bad":"整批差时写：和这个方向之前跑起来的素材比，内容具体差在哪，推测写成推测","op":"这批钱在哪些户、哪组投手，投手那两天做了什么和这批有没有关系","next":"下一步"}`。绿的写 good，红的写 bad，红的批次里有跑起来的也写 good。全盘当天的操作写在「__day|MM-DD」：`{"op":"..."}`。good、bad、op 都按总分写（Reina 11/5）：第一行一句话直接说结论，页面加粗；后面每行一条细节，页面显示成列表。verdict 回答的是「这批为什么没跑起来（或为什么比大盘好）」。两天合计不到一条大盘的钱才写「钱太少看不出内容」，其他红的批次都要和之前跑起来的素材比内容；第三天放量到当天大盘 5 倍以上的单条要写出来，钱在哪些户也要写。金额带 ¥ 和千分位，次留带 %，列账户只列前 2 户。页面点柱子展开就是这些内容。
- 标红（Reina 11/5 定）：notes/batches.json 里比较确定的严重问题，把关键那几个字用 `==…==` 包起来，页面上标红。比如录屏和讲的事对不上、字幕没提 Today、次留好的头条第二天被卡、低次留的户吃了大头、成本异常。写「推测」的不标，样本小的单条次留不标，每批最多标 2 到 4 处，不标整段。红字要写成别人一看就懂的结论，不标孤立的数字（Reina 11/5：「这批照真人版第二天 ¥4」别人看不懂）。
- 点开柱子的「这天留存为什么差」和按批次次留的趋势卡（Reina 11/6）：schedule_data 的 rt_diagnose 按分日表自动算，不用手写。低于大盘 1 点以上，或比自己前 3 天（相对大盘）掉 3 点以上才出；激活不到 100 不算，差距在误差内写不归因。每条素材分：新内容（首花 3 天内或没历史）、一直低还在花、掉了（衰退）、放量买便宜量；3 条以上同一天掉算投放或流量。全盘这一格拆成老素材自己掉和新素材、结构。贡献加起来等于总差。账户层不在里面，账户动作还是看全盘这一格的投手操作。柱子、柱子悬停卡、点开的留存表都按首花日（Reina 11/6，不再按 0–3、4–7 天分批）：柱子每段一个首花日，颜色越深首花越近；表和卡片每个首花日一行，带在跑条数和激活，不合并。趋势卡是这一行同样几条素材往前 10 天，激活不到 30 的天不画。
- 录屏助手名不算问题（Reina 11/6）：用户可以给自己的助手取名字，不取名才显示 Today。录屏顶部、输入框、底栏写小芽、Chuck、个人助理这类名字都正常，不写「不是 Today」，不标红，不要求改。scripts/ 里旧 note 还写着「不是 Today」的，不当问题引用。
- 评价执行、下形式的结论（比如 AI 照真人不如真人重配）（Reina 11/5）：先读当时给的要求（A 表这一行的「怎么改」「不能拍的」和迭代方案），再看片按要求逐条核对。要求里没写的不算问题，不拿原版的台词、镜头逐句比，照真人不是 1:1 复刻。没按要求做的写没做到，这几条不算进形式结论；按要求做了还跑不好，才能说形式。内部字样、错字幕另外单独写。只看了画面字幕、没听声音的，不写配音缺了什么。
- 点柱子的面板和悬停卡片会自动写留存（schedule_data 的 ret、batch_items 的 a0、r0、at、rt）：这个方向当天留存（悬停卡片括号里写比大盘高或低百分之多少，Reina 11/6 要，按相对大盘的比例算，不是个点）、当天大盘留存、新上素材留存、按批次留存，都是当天激活的人。最新一天写还没回传完，前一天写可能偏低约 1 个点。
- 写 notes/schedule-T.json：`{"day":"MM-DD","summary":"一两句总的判断"}`。下面那张表从 notes/batches.json 取。schedule_build 读它放进回收那一节。

进度口径（11/6 改）：实交取扩量素材名条数和迭代素材成片附件数的大数，素材名没填全的不算落下，写进 groups.X.name_gap 和草稿最后一句。B 组扩量排期第一个到期日之前，脚本表和二剪表每行算一条；之后只按排期行算，AI 行素材名没填的用同 use case 已有成片的脚本行补。脚本表、二剪表没写产出日期的行不算到期，不带上一行的日期。
落下了怎么办：progress.json 的 groups.A.lag、groups.B.lag 是落下的行（行号、use case、差几条）。只推给 Reina，把 draft.A、draft.B 附上，这是可以直接发给唯西两个素材群的提醒草稿，发不发、怎么改她定。不自己发群，不改飞书，草稿不带看板链接。

schedule_read.js 只返回算进度要的字段和最近 10 天的行，脚本及成片按 use case 和完成时间合起来（11/2 起 A 组这张表的 UC_ID 列没填，从素材命名或成片文件名里取 UC）。11/4 在 6 个 tab 上真跑过。

排期内容只在 tools/schedule_plan.json，页面不手改：
- E 是排期条目：d 交付日、g 组、t 类型、n 条数、s 状态（done 已交没花钱、todo 待交、cut 建议拿掉、add 建议加）、src 和 link 是飞书位置、to 是拿掉后怎么办。另有四个字段给「点未来排期的数字」弹窗用（Reina 11/10）：sc 细分场景、k 类型（变式 / 同脚本换画面 / 自己发挥 / 空）、tpl 照哪个头部模板、how 一句话做什么（变式写「这次换（换人设）：…」）。往飞书排期加行、改行时同一次把这四个字段写进 E，src 的行号要和飞书表对上（11/9 晚 A 表第 132 行插过一行，之前 E 里 A 组第 142–164 行的行号整体差 1，11/10 已改）。已上线的条数从数据算，不写在这里。
- Reina 确认调整、写进飞书之后，把对应条目改掉（add 改 todo，cut 删掉或换 uc），MOVES 也跟着改，asof 改成当天。
- 表里写了「先不拍」「顺延」（开头的【】或脚本备注）的行不算该交。B 组二创那张表没有备注列，这种行写进 plan 的 skip_rows。
- 每周一换新一周：week、asof、sub、meters（已排 / 本周产能）、E、MOVES、MT、GROUPS 都要更新。换之前先把上一周的产出目标（ai、ec 取上一周 meters 的合计，xg、kol 取 output_targets）写进 targets_by_week[上周一]，周一页面看上周产出时用它，不然会拿新一周的目标去比。week 和 T 所在那周对不上时，页面不显示产能条、结论和要改什么，脚本打 WARNING。
- schedule/2026-11-04/ 是 11/4 手工定稿版（schedule-source=manual），不覆盖，也不重算。

页面日期都按 D 和 T 算：柱子是 D 往前 14 天，排期列是 T 到 T+4。过了日子的 todo、cut、add 不再算进后面的供给，看进度那一行；已交没花钱的挪到今天，asof 之后上线的条数扣掉。

口径（schedule_data.py）：
- 批次日期 = 首花日，这条素材第一天有消耗（Reina 11/5 定，和日报一致）；分日表最早一天就花钱的用上传日（素材ID >> 32 是秒，加 8 小时）。同名的推送版、修改版（前缀 推送视频_，后缀 _合规修改、修改版、_改动、 (1)）和同一脚本编号（如 A18-06-cw-20261023）算同一条，取最早。
- 条数只算花过钱的。c7 = D-6 到 D 的消耗；次留率、次留成本看 D-6 到 D-1。
- PS03 表里一行，三部分按素材映射 J 列分，写在执行细节。还是库外、靠 FUZZY 归 PS03 的算消息排清单。
- 单条跑量：首花 D-7 到 D-2 的素材（不早于 STABLE = 10/29：10/28 那批赶上预算放开，后面的批次到不了），前 3 天消耗按全盘一天 ¥15 万折算后的条均。sh 是近 7 天消耗占比，np 是 D-14 到 D-1 首花的条数占比。放量 = 单日 ≥ ¥2,000。
- 预计下降额：第 2 天以上、最近 2 天日均 ≥ ¥100、峰值在最近 2 天、第一次单日 ≥ ¥200 在 D-5 之后的素材，最近 2 天日均 × 50%（DROP），算在首花 + 4 天，早于 T 的算 T。第 0–1 天的新素材不算下降，算进预警的「到的条数」（n01）。回测 10/22–11/1：第 4 天日均 ≥ ¥1,000 的素材除全盘后还剩 40%，全部素材还剩 46%；第 0–1 天日均 ≥ ¥100 的后 3 天 1.2 倍。
- 预警（schedule_data.py 的 flow）：页面只显示红色警告，不显示金额。这天预计掉的比补的多，差额超过 ¥500 和现在消耗的 10%（全盘 5%），现在消耗不到 ¥1,000 的不标。补的按 CURVE 算，AI 和二创分开，每条每天取这个方向这类素材前 3 天日均，不足 5 条用这类素材全盘的。前两天刚上的素材按实际跑量校正。待交的按交付第二天首花。
- 回收（schedule_data.py 的 recover）：前 3 天（D-3 到 D-1）放出的素材，按方向和 AI、二创分行，3 条以上才列。跑起来 = 首花第二天，花得比当天大盘平均每条多（全盘消耗 ÷ 在跑条数，schedule_data.py 的 is_up）。不定绝对值。预期 = 这个方向这类素材之前跑起来的比例 × 条数。5 条以上且碰巧概率 <10% 才标不及预期、超预期。可能见顶 = 不及预期 + 最近 3 天占比没涨 + 7 天内上了 10 条以上。
- 要看片的素材（recover 的 bad）：首花 7 天内，激活 ≥100，次留比同样这些天的全盘低 5 个点以上，配底稿。Reina 11/5 定：use case 的性质不因一批素材改，新素材差要下钻内容，不打在 use case 上。下钻顺序见项目文档 claude/new-batch-retention-drill-1105.md。
- 批次回收（schedule_data.py 的 batches）：每个首花日几条、几条跑起来、第二天花多少。柱子下面的条数按它标色：这批第二天平均每条比当天大盘高绿色，低红色，3 条以上才标；页面顶部一行写前天首花这批第二天每条花多少。
- 在跑：当天花了钱的条数，按批次分，悬停柱子看。
- 分档（schedule_data.py 的 tier_stats，schedule_build.py 的 tier_view）：线写在 schedule_build.py 的 UP_*、IN_*，定义见 claude/usecase-tiers-1104.md。探索过线标「可升」，跑量少 + 留存好过升级线也标「可升」。可升的直接升（Reina 11/9 定，不用再问）：每天出页面后看有没有 can 为 true 的 use case，有就改 schedule_plan.json 的 GROUPS 升一档，在 MOVED 写从哪档来、哪天，重跑 schedule_build，7 天内名字旁标「新进」，最后回复里写升了哪几个。只升不降，降档还要 Reina 定。在本档里地位危险的标「危险」（Reina 11/9，schedule_build.py 的 tier_view 自动算，只标不降）：两档都看近 7 天（激活 ≥100），次留比全盘低 1.5 个点以上或成本贵 ¥3 以上，就是第二档的退出线；第一档另外看近 7 天占比掉到 3%（RISK_SH）以下。探索没有危险。悬停名字看是哪条线。连续两周危险的，在周报里提给 Reina 定降不降。
- 点 use case 名字弹出历史素材（Reina 11/9）：schedule_data.py 的 history() 把分日表里所有花过钱的素材按 use case 列出来（推送版、修改版合成一条，总消耗倒序），schedule_build.py 的 hist_view() 配视频和原帖链接，模板里 histOpen() 画弹窗，可按 AI/二创筛、点表头按首花、消耗、次留、成本排。次留和成本只算到 D-1。链接和回收表一样来自 tools/links.json，巨量签名链接 2 天过期，所以只有最新一天的页面链接全。
- 历史素材弹窗的细分场景和悬停卡（Reina 11/9）：每条素材的场景取 notes/scene-map.json（日报第五节每天打标会累积；11/9 把 10/11 起花过钱、还没打的 607 条一次补齐），弹窗顶上按 tools/scenes.json 算这个 use case 测了几个场景、覆盖率，每个场景一块（条数、消耗、次留，灰色没测），点了只看这个场景。总消耗悬停是逐日消耗柱状图，次留悬停是逐日次留折线（激活不到 20 的天不画，虚线大盘），数据是 history() 的序列和 base。视频链接缺的去唯西「Today-日报」的（总）素材每日分版源数据 DDNSK0（媒体素材ID、素材预览两列，tos.mobgi 永久链接）补进 tools/links.json 的 video；11/9 补了 136 条。
- 排期分散（Reina 11/9）：同一个 use case 一天最多 6 条（A、B 两组、AI 和二创合计，含上周留下的存量行），多出来的往后一天挪；不要一天一个方向挤十几条。
- 条数建议只看能不能跑量，不看留存。阈值在 schedule_build.py 的 rule_rows，和 11/4 定的一样，先跑 1–2 周。schedule_build 输出的 all 是全盘预警的天，red 是 {use case: 预警的天}。

次留、成本的趋势卡（Reina 11/6 要）：鼠标放到某一行的次留或成本上，看最近 7 天折线，虚线是大盘。最新一天次留没回传不画，激活不到 30 的天不画，表里「比大盘」按相对比例算。

知定堂星广（Reina 11/6，11/9 更新）：新 agency，KPI 每周 80 条（Reina 11/9），从 11/9 这周起星广目标在原来的 15 条上加 80，output_targets 的 xg 是 95；三档 50/30/20，单独测星广；产品新增浏览器操作能力，use case 库要更新，另外 50 条等库更新后再排。排期放他们的飞书表，看板不单独放一块（Reina 11/6），也不写进 schedule_plan.json。飞书表建好后，接进 schedule_read、schedule_progress（第三条进度条）和 schedule_output（星广预计已按 95 算，知定堂的成片要读进来才算完成）。

本周实际产出（Reina 11/5 要，在页面最上面）：昨天和本周累计，四类 AI 素材、真人二创、星广、达人合作，累计对比预计和完成度。
- 除了上面 6 个 tab，schedule_read.js 还要跑 A 组 lheDJa（星广脚本审核表）、L1c0HC（付费达人执行表）和悦普执行表 https://my.feishu.cn/wiki/OmjFw42Tpiq8lykD9zzclekTnfd?sheet=5cypAT（现在是 11月执行表，每月一张，换月要换 sheet id，存文件名还用 5cypAT.json），存进同一个目录。再读 'Today KOL/KOC 视频'!A1:Z 存成文件。然后 `python3 tools/schedule_output.py --dir /tmp/sched/feishu --koc <视频文件> --date T --out /tmp/sched/output.json`，schedule_build 加 `--output /tmp/sched/output.json`。
- 类型（Reina 11/5 定）：水下达人原片都要剪了再投，不当投放素材类型，10 月中的老原片只留在数据里，不算产量。达人合作数的是发布的视频条数，不是投放素材。
- 按实际产出日算，不按排期日期：AI 和二创看完成时间和文件名最后一个日期，再空看产出日期；星广看成片完成时间；达人看发布日期（唯西发布时间、悦普已发布的发布档期、其余代理商「Today KOL/KOC 视频」），图文不算。类型看扩量表「怎么改」的【AI】【二创/重配】，没写的老行看文件名。文件名没有日期的行写进 output.json 的 undated。
- 预计：AI、真人二创用这周产能（plan 的 meters 第三列，Reina 11/10 定：11/9 这周起 A 组 AI 150、真人二创 100，B 组 AI 100、真人二创 100，合计 AI 250、二创 200）；星广 95（唯西 15 + 知定堂 80，11/9 起）、达人 65（外部 50 + 唯西 15）在 plan 的 output_targets，取自素材产出日报。meters 的 week 对不上时 AI、二创退回 150、50。
- 水上：合作形式以「星图」开头的抖音合作，只算唯西和悦普；AnyMedia 的表没读，不知道水上水下。
- 和素材产出日报的数会不一样：日报的 AI 只算 A 组脚本及成片，不算扩量表和 B 组，不算二创，外部 agency 没有悦普，发出后补填的日期也不回改。

页面排版（Reina 11/5 要小字少、看图清楚）：顶上左边本周实际产出，右边「今天要看」只放要动手的：A、B 组对照排期的进度条（Reina 11/6 要，取代 B 组速度那一行）、落下几行、预计会跌、可能见顶、要看片，每项一行（Reina 11/5：不需要这么多东西，两块高度对齐，不占位置）。定义和口径都放进折叠的「规则和口径」，页面上不再常驻解释性小字，新加内容也照这样放。

## 素材产出看板（Reina 11/10）

两组每天交的素材统一放在 output/（output/ 是这周，output/<周一>/ 按周归档，目录 outputs.json），日报、周报、排期页导航里都有「素材产出」。分类：头部模板变式（照「头部素材结构提取和变式（11/9）」22 个模板做的，含同脚本换画面），目标占 70%、每天至少 20 条；新测试约 30%；只换前贴（只换开头 hook 画面，名字里写「换前贴」）的不算数。另有 AI / 二创、一级分类、use case、细分场景几个维度，每条都链到飞书里的成片那一格（?sheet=…&range=列行的 base64），已经投出去的再带巨量视频和累计消耗。

1. 内置浏览器打开下面 5 个 tab（带 ?sheet=），用 javascript_tool 跑 tools/output_read.js 全文，跑之前把 SINCE 改成 D 的 MMDD（每天只读昨天和今天交的，旧的已经存在 notes/output-items.json；周一改成上周一，全周重读一遍）。返回的文本原样存成 /tmp/out/<tab id>.tsv。
   - A 组 https://ecn9dk42chzo.feishu.cn/wiki/O1kqwF3CqiguXQkNuTbcOew0nNc ：kMJdAv 扩量素材迭代排期、f18d7b 脚本及成片
   - B 组 https://ecn9dk42chzo.feishu.cn/wiki/UKghwNDuNiRtPRk82vwcwylwnAb ：3KtioB 扩量素材迭代排期、c665d9 脚本&成片、EnYgPG 真人素材和ai切片二剪
   同一个域名下可以把脚本存进 localStorage（键名 __claude_ 开头，用 AsyncFunction 跑，结束时删掉），不用每个 tab 都贴一遍。
1之二. 还没成片的脚本（Reina 11/11，只看最新时间点，不追溯过去，只放进当周页面）：在 A 组 f18d7b、kMJdAv，B 组 c665d9、3KtioB 四个 tab 用 javascript_tool 跑 tools/script_stage.js 全文（同域名可以先存进 localStorage 键 __claude_stage、用 AsyncFunction 跑，跑完删掉），返回的 JSON 原样存成 /tmp/out/stage_<tab id>.json（不要手抄，从会话记录里解析工具结果写文件）。口径：「脚本状态」需修改、修改后待审核、未审核 = 还在脚本中；可制作、「成片」空着、交付日在本周 = 脚本已完成、还没开始做（以前的、几个月前一直没做的不算）。说了不要做的、弃用的不算：脚本备注或对应扩量排期行写了先不拍、不用拍、弃用、顺延这类。交付日：A 组按脚本名里写的扩量排期行号（-75-、76行、【60】、_158_）取那一行的日期，热点按名字里的 MMDD，都没有沿用表里上一条的；B 组按产出日期，没有就按 3KtioB「45，46脚本已贴表」写到它的那一行。A 组从第 485 行读，B 组全表。成片没回填、但同 use case 同标题素材已经交了的挪到 done。没读到就沿用 notes/output-stage.json。
2. `python3 tools/output_build.py --dir /tmp/out --date T --sheet <投放数据_分日文件>`：合进 notes/output-items.json（按组 + 素材名去重，同一条在扩量表和脚本表都登记的留扩量表那条），重写这周和上周的页面。
3. 提交 output/、outputs.json、notes/output-items.json、notes/output-stage.json。
- 分类规则：扩量表那一行「怎么改」或「依据」写了「头部模板」的算变式；名字带「同脚本换画面」的算同脚本换画面；名字带 22 个模板原片标识（output_build.py 的 TEMPLATE_KEYS）的也算变式；其余算新测试。新加头部模板时把它的原片标识加进 TEMPLATE_KEYS。
- 细分场景：扩量表取那一行的细分场景；脚本表没有这一列，投出去以后从 notes/scene-map.json 补。
- 头部模板变式的「细分场景」写换了什么（Reina 11/10）：先取素材名里模板标识后面的变量（如「LOL比赛」），再按「换角度+NN」对上 tools/templates.json 里这个模板的第几个角度，再取排期行「怎么改」里写的「这次换（…）」，都没有就写「没写变量，原片场景：…」。换了 use case 的写「换 use case：…」。
- 只算审核通过的（Reina 11/10）：output_read.js 第 13 列读这一行的「成片状态」，只有写「通过」的才计数、才放链接；需修改、修改后待审核、待审核、没填的都折叠在当天「交了但还没通过」里，不算数也不放链接。B 组扩量表没有成片状态列，用脚本表/二剪表同名那条的状态。
- 成片链接（Reina 11/10）：没投的链飞书表里成片那一格，投出去以后自动换成巨量/唯西日报的永久视频（每天跑 output_build 时按分日表的素材名对上）。飞书附件直链会做 Referer 校验，从看板点开报「Referer check fail」，不能用。output_read.js 第 12 列的 fileToken 先留着。
- 这页是统一管生产批次和实际成片的地方（Reina 11/10）。「每天的成片」按天倒序列实际交的成片（素材名直接链到飞书成片），每天下面折叠着这天还排着没交的计划，不放表里行号。计划的数据来源： schedule_plan.json 里这周的排期行当批次（排了几条、哪天交），扩量表交的成片按行号挂上；脚本表、二剪表交的按组、use case、AI/二创、是不是变式，挂到交付日当天或前两天的排期行，对不上的算「排期外」。所以往飞书排期加行时，E 一定要同步加，不然这里对不上。

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
 "uc": {"UC_ID": "这个 use case 下周做什么"},                               // 表里 T1、T2、T3 每个一句
 "l1": {"一级分类": "这个分类下周做什么，一句"},                          // 第二部分「一级分类」，周消耗占比 ≥ 0.5% 的每个写一句
 "wk_market": [{"t": "结论", "d": "依据，要和上周周末比"}], "wk_top": [{"t": "结论", "d": "依据和下周怎么试"}], "wk_names": {"素材ID": "头部素材短名"},  // 第一部分「周中和周末」，分大盘和头部素材，先写结论再写依据，小标题必须是一句结论，不能只写一个词；先按上线天数拆（wk.age）、看同一批素材过周末（wk.carry、wk.batch），再下分类结论，新老素材混着看会把新素材的跌算到分类头上；周五激活的人周六回访，周五也算周末；上周周中被单日拉低要说明，不能只比均值；说放量造成要有同批素材加量才跌的证据；每个一级分类写清老素材和新素材各自怎么变，标签用老素材好、新素材跌、新老都跌、两条拉高、样本小（四个字以内）；老素材好要先去掉最大的一两条再看；"wk_tags": {"一级分类或素材ID": "周末多投/周末压/看不出/样本小"}
 "rules_note": "规律的依据范围一句",
 "rules": [{"t": "规律 + 下周怎么做", "d": "依据：每组多少条、次留率、次留成本、连续 3 留，少于 5 条的只说方向"}],  // 第六部分「头部和拖后腿素材的规律」，3 到 6 条，不摆脚本
 "output": {"note": "各类型按什么日期算", "rows": [{"t": "类型", "n": 产出, "plan": 计划, "live": 上线投放}]},  // 每周都要写（Reina 11/9）。行：唯西 AI 短剧、唯西星图达人、外部 agency KOC/KOL、唯西星广、唯西自建号、合计（不含二创），数和增长小群周一那条「素材产出日报」的上周合计对齐。唯西自建号：产出按唯西进度表「自建号脚本与成片」(?sheet=UJsWF1) 的成片完成时间，计划 20/周，上线投放 = /tmp/week.json 的 kind 里「唯西自建号」的 n_new（见上面「唯西自建号」一节；11/2 那周 0）；巨量里的素材名是抖音发布文案，按素材ID 对，不按名字  // 素材产出数量，放第五部分。小红书、抖音从「Today KOL/KOC 视频」按发布日期数；AI、唯西星图达人、自建号、星广按唯西表和素材产出日报；二创和上线投放从「投放数据_分日」按首次消耗数；计划按素材产出日报，二创计划按「每周素材追踪」
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


## 悬浮目录（Reina 11/9：所有页面都要有）

日报模板 tools/template.html 自带目录（id="toc"）。周报、排期、专题页用 tools/toc_snippet.html（id="gtoc"，按页面 h2 自动生成），已经插进 tools/week_template.html、tools/schedule_template.html 和现有页面；新做的专题页或别的手写页面跑一次 `python3 tools/add_toc.py <页面>`。改目录样式改 toc_snippet.html 后，再对所有页面跑 add_toc.py 换成新版。

### 扩量排期表按日期摆（Reina 11/10）
- 改排期时新行插回对应那天的块里，不往表底下追加新的一块；同一天只有一个日期标题，标题写「M/D 周X（AI a 条、二创 b 条，共 n 条；其中头部模板变式 v 条）」，那天在上面别处还有行就写「另有上面第 N 行 …」。
- 日期列每一行都填，不跳着填（Reina 11/11）：一天的第一行写上面的完整标题，这天后面的行也写「M/D 周X」，「下周」块每行写「下周」，不留空、不靠合并单元格往下带。往 A、B 组飞书表加行、改行、重排都照这个做。
- 已经乱了就用 tools/schedule_reorder.js 重排：只动从某行起（A 组 kMJdAv 第 147 行、B 组 3KtioB 第 57 行）还没开工的行，按 11/9 → 11/10 → 11/11 … → 下周 排，标「顺延到下周」的放进「下周」块，说明行放在第一个未来日之前；有附件/素材名/成片状态的行它会停下不动。先 WRITE=false 看映射，再写；写完等 10 秒以上再刷新核对（刷得太快会看到旧数据）。写完按它返回的「旧行>新行」改 schedule_plan.json 的 src 行号，并按 UC 逐条核对。
- 唯西也会在表里插行删行（11/10 上午 A 组第 104–131 行之间少了 2 行），所以每次动表前先按 UC 核对 schedule_plan.json 里的行号。

## 排产衔接检查（Reina 11/11，每天上午）
- 目的：最近三天起量、表现好的 use case 和刚跑出来的头部模板素材，后面几天排产要接得上，不能表现突然很好、后面没排。
- 数据：python3 tools/align_check.py --sheet <投放数据_分日> --date D --page D/index.html --out /tmp/align/data.json（口径写在脚本开头）。
- 排期：A 组 kMJdAv、B 组 3KtioB 里日期 T+1 到 T+3 的行（当天不动），按 UC_ID 和「怎么改」里照的原片/模板合计条数；头部模板表 my.feishu.cn/sheets/VEBUs3HTjh3dHqtojlsckJzmnqS 看新赢家进没进表。
- 接不上的判断：起量 + 表现好的 use case，后三天 A+B 合计排产占比明显低于它近 3 天消耗占比（低一半以上），或后三天里有一天是 0；新跑出来的模板素材后两天没有变式。
- 只有需要调整时才发飞书「投放同步群 A+B」（群里有唯西两组投放和 Xuhan，Reina 11/11 改），没有就不发。只建议，不改排期表；群里有代理，不放看板链接。
