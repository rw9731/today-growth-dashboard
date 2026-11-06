# Today 投流素材看板

- 统一链接：https://rw9731.github.io/today-growth-dashboard/ ，默认是最新一天的日报
- 往期：页面顶部「日报」下拉，或直接打开按日期的文件夹（如 2026-10-27/）
- reports.json：往期日报目录，每次生成新日报时更新，旧页面也读这份
- schedule/：素材排期看板，schedule/ 是最新一天，schedule/<日期>/ 是往期；schedules.json 是目录
- topic/：专题分析，topic/ 是目录页，topic/<日期-主题>/ 是每一篇；日报、周报顶部「专题」一行进去。专题页把汇总数据直接写在页面里，不随日报更新
- tools/：每天生成日报用的脚本和页面模板，步骤见 tools/RUN.md

页面只放汇总后的结果，不放原始分日数据。
