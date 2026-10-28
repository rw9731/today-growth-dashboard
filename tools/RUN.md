# 每天生成日报

D = 新加坡时间昨天（报告日）。数据：Google 表「国区投放素材」(1LHsOHd5U7Ep0SHF-XQecIE-wj9FN2JireiPFhvp3t0Q)，「投放数据_分日」每天 10:13 左右更新到 D。

1. 读 `'投放数据_分日'!A1:AA` 和 `'素材链接库'!A1:D`（get_values，结果存成文件）。
2. `python3 tools/compute.py --sheet <分日文件> --linklib <链接库文件> --date D --out /tmp/results.json`
   - 输出 `NO_DATA`：表里还没有 D，等 20 分钟再读。
   - `unknown_uc` 不为空：在「✅ Use case 库」找到这些 UC，把 `{"short": 4–8 字简称, "l1": 一级分类, "l2": 二级分类}` 加进 tools/ucs.json，再跑一次。
3. `python3 tools/build.py /tmp/results.json`：写 D/index.html，更新 reports.json；D 是最新一天时同时改 index.html。
4. 提交 D/、index.html、reports.json（和改过的 tools/ucs.json），push 到 main。

口径：消耗看 D；次留率、次留成本看 D-3 到 D-1 激活的人（巨量次留记在回访那天）；标签和全盘三天比。门槛在 compute.py 的 TH。
