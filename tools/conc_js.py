"""素材集中度（Reina 11/11）：昨天每条素材在单个账户里最多花了多少、占它总消耗多少、在几个账户里花了钱。

用法：python3 tools/conc_js.py --date D --out /tmp/linkjs  → 写 /tmp/linkjs/conc.js
在内置浏览器打开 https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746 （巨量升级版工作台，跳到登录页就停，不输账号密码），
用 javascript_tool 跑 conc.js 全文，返回值是一段 JSON 字符串，原样存成 /tmp/linkjs/conc.json（不要手抄，从会话记录里解析工具结果写文件），
再跑 python3 tools/conc_save.py --date D /tmp/linkjs/conc.json，写出 notes/conc-D.json，compute.py 默认读它。
只调查询接口，不点任何按钮。这个接口一次返回当天全部「素材 × 账户」行，分页参数不起作用，只调一次。
口径：按账户算（接口不支持按项目拆，一个账户下可能有几个项目），只算 D 当天有消耗的账户。
"""
import argparse, os

JS = r"""// 在这个页面跑（巨量升级版工作台，要已登录）：https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746
{ const D = "__D__";
const b = {sophonxType: 3, appKeys: ['0', '80', '10168'], dataSetKey: 'EBP_management_mid_analysis', metrics: ['stat_cost'], dimensions: ['material_id', 'advertiser_id'], filters: {ConditionRelationshipType: 1, Conditions: []}, startTime: D, endTime: D, orderType: 2, orderField: 'stat_cost', advertiserIds: [], needBpList: true, componentType: 1, extra: {delivery_mode: '1'}, ebpids: [], pageParams: {Limit: 50, Offset: 0}};
const j = await (await fetch('/api/ebp/common/sophonx/get_material_sophonx_data?ebpid=1878449164572746', {method: 'POST', credentials: 'include', headers: {'content-type': 'application/json'}, body: JSON.stringify(b)})).json();
const t = j.data && j.data.tableList, L = (t && t.list) || [];
const M = {};
for (const r of L) { const c = parseFloat(String(r.stat_cost).replace(/,/g, '')) || 0; if (c <= 0) continue; (M[r.material_id] = M[r.material_id] || []).push(c); }
const rows = Object.entries(M).map(([m, a]) => { a.sort((x, y) => y - x); const s = a.reduce((p, q) => p + q, 0); return [m, Math.round(s), Math.round(a[0]), a.length]; }).filter((r) => r[1] >= 100);
JSON.stringify({date: D, code: j.code, total: t && t.pagination && t.pagination.total, got: L.length, d: rows.map((r) => r.join(',')).join(';')});
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'conc.js'), 'w').write(JS.replace('__D__', a.date))
    print('{"date": "%s", "page": "https://business.oceanengine.com/ebp/material/analysis/video?ebpid=1878449164572746"}' % a.date)


if __name__ == '__main__':
    main()
