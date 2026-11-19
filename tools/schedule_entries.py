from datetime import date, timedelta


def is_deferred(entry):
    return '顺延' in (entry.get('to') or '')


def planned_entries(plan, week=None):
    """排期看板和路线图共用的已排条目。week 为周一日期，省略时取全部周。"""
    end = (date.fromisoformat(week) + timedelta(days=6)).isoformat() if week else None
    return [
        entry for entry in plan.get('E', [])
        if entry.get('d') and entry.get('s') != 'cut' and not is_deferred(entry)
        and (end is None or week <= entry['d'] <= end)
    ]
