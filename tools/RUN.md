# 每天生成日报

D = 新加坡时间昨天（报告日）。数据：Google 表「国区投放素材」(1LHsOHd5U7Ep0SHF-XQecIE-wj9FN2JireiPFhvp3t0Q)，「投放数据_分日」每天 10:13 左右更新到 D。

1. 读 `'投放数据_分日'!A1:AA` 和 `'素材链接库'!A1:D`（get_values，结果存成文件）。
2. `python3 tools/compute.py --sheet <分日文件> --linklib <链接库文件> --date D --out /tmp/results.json`
   - 输出 `NO_DATA`：表里还没有 D，等 20 分钟再读。
   - `unknown_uc` 不为空：在「✅ Use case 库」找到这些 UC，把 `{"short": 4–8 字简称, "l1": 一级分类, "l2": 二级分类}` 加进 tools/ucs.json，再跑一次。
3. 补链接（要用 Reina 电脑上的内置浏览器，连不上就跳过）：`python3 tools/links_js.py /tmp/results.json --out /tmp/linkjs` 生成几段 JS，每段在它第一行写的飞书页面里用 javascript_tool 跑，返回的 JSON 存成同名 .json；然后 `python3 tools/links_merge.py /tmp/linkjs`，再跑一次第 2 步。原片 = 唯西表「真人原素材」的博主发布链接，成片 = 唯西表「脚本及成片」里那一格，预览 = 唯西日报里的巨量素材视频。
4. `python3 tools/build.py /tmp/results.json`：写 D/index.html，更新 reports.json；D 是最新一天时同时改 index.html。
5. 提交 D/、index.html、reports.json、tools/links.json（和改过的 tools/ucs.json），push 到 main。

已经发布的日子只补链接、不重算：`python3 tools/relink.py YYYY-MM-DD`。

口径：消耗看 D；次留率、次留成本看 D-3 到 D-1 激活的人（巨量次留记在回访那天）；标签和全盘三天比。门槛在 compute.py 的 TH。
