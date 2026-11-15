"""星广视频的链接和名单（Reina 11/15：消耗排行里的星广、自建号都要有视频链接）。

1. python3 tools/star_js.py --out /tmp/linkjs  → 写 star.js
   在 https://business.oceanengine.com/ebp/material/management/star-task?ebpid=1878449164572746 （巨量升级版工作台，只读）
   用 javascript_tool 跑 star.js 全文，返回值原样存成 /tmp/linkjs/star.json（从会话记录里解析工具结果写文件，不手抄；太长会被存成文件，从那个文件里解析）。
2. python3 tools/star_merge.py /tmp/linkjs/star.json
   把每条星广视频的抖音作品链接写进 tools/links.json 的 video（永久链接，页面上的「视频」），
   素材名（抖音文案）补进 notes/names.json，素材ID → [文案, 抖音号, 任务ID] 写进 notes/star.json（素材类型分「唯西自建号」「唯西星广」「知定堂星广」靠它）。
任务在 TASKS 里；新开了星广任务（星广联投 → 任务管理里多一行）就把任务ID 加进去。
"""
import argparse, datetime as dt, json, os

TASKS = {'7702316618969333810': 'Today-唯西星广', '7706501371755200522': '知定堂星广', '7706732258950479882': 'Today-ZD-1111'}

JS = r"""// 在这个页面跑（只读）：https://business.oceanengine.com/ebp/material/management/star-task?ebpid=1878449164572746
{ const TASKS = %s, START = "%s", END = "%s";
const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
const out = []; const err = [];
for (const tid of TASKS) { for (let p = 1; p < 30; p++) {
  const b = {sophonxType: 0, appKeys: [0], dataSetKey: 'ebp_ad_star_task_video', metrics: ['stat_cost', 'active'], dimensions: ['material_id', 'star_video_title', 'star_video_play_link', 'star_video_status', 'star_ies_aweme_id', 'star_ies_nickname'],
    filters: {ConditionRelationshipType: 1, Conditions: [{Field: 'star_task_id', Operator: 1, Values: [tid]}]}, startTime: START + ' 00:00:00', endTime: END + ' 23:59:59', orderType: 1, page: p, limit: 50, needBpList: true, componentType: 1, extra: {is_fill_zero: 'true', original_adv_id: '1878224050570252'}};
  const j = await (await fetch('/api/ebp/common/sophonx/get_material_sophonx_data?ebpid=1878449164572746', {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json', 'x-csrftoken': csrf}, body: JSON.stringify(b)})).json();
  if (j.code !== 0) { err.push(tid + ' ' + j.code + ' ' + (j.msg || '')); break; }
  const t = j.data && j.data.tableList, l = (t && t.list) || [];
  for (const r of l) out.push([r.material_id, tid, r.star_video_play_link || '', r.star_ies_nickname || '', r.star_video_status || '', (r.star_video_title || '').slice(0, 80)]);
  if (!(t && t.pagination && t.pagination.hasMore)) break; } }
JSON.stringify({STAR: 1, err, items: out});
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    t = dt.date.today()
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'star.js'), 'w').write(JS % (json.dumps(list(TASKS)), (t - dt.timedelta(days=45)).isoformat(), (t - dt.timedelta(days=1)).isoformat()))
    print(json.dumps({'tasks': len(TASKS), 'js': os.path.join(a.out, 'star.js')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
