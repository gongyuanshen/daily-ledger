"""Android boundary for the unchanged desktop ledger; JSON money and IDs are strings."""
import json
import re
import sqlite3
import sys
import traceback
from calendar import monthrange
from contextlib import closing
from datetime import datetime
from pathlib import Path

from ledger import Ledger, format_amount, parse_amount, parse_day


def money(units):
    return format_amount(units).replace(',', '')


def text(payload, key, *, nonempty=False):
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f'{key} 必须是文本。')
    value = value.strip()
    if nonempty and not value:
        raise ValueError(f'{key} 不能为空。')
    return value


def identifier(payload, key='id'):
    value = text(payload, key)
    if not re.fullmatch(r'[1-9][0-9]{0,18}', value) or int(value) > 9223372036854775807:
        raise ValueError('记录编号必须是有效的正整数文本。')
    return int(value)


def month_text(payload):
    value = text(payload, 'month')
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}', value):
        raise ValueError('月份格式应为 YYYY-MM。')
    parse_day(value + '-01')
    return value


def filtered_rows(book, payload):
    args = {}
    for key in ('start_day', 'end_day', 'category', 'payment'):
        args[key] = None if payload[key] is None else text(payload, key, nonempty=True)
    args['keyword'] = text(payload, 'keyword')
    return book.list_entries(**args)


def rows_result(rows):
    return {'entries': [dict(id=str(row['id']), day=row['day'], amount=money(row['amount_units']),
                             note=row['note'], category=row['category'], payment=row['payment']) for row in rows],
            'amount': money(sum(row['amount_units'] for row in rows)), 'count': len(rows)}


def dispatch(book, action, p):
    if action == 'bootstrap':
        today = parse_day(text(p, 'today'))
        daily = book.list_day(today)
        summary = book.month_summary(today[:7])
        return dict(today=today, month=today[:7], today_amount=money(sum(r['amount_units'] for r in daily)),
                    today_count=len(daily), month_amount=money(summary['total_units']),
                    month_count=summary['count'], categories=book.categories(), payments=book.payments(),
                    python_version=sys.version.split()[0], sqlite_version=sqlite3.sqlite_version)
    if action == 'entries':
        return rows_result(filtered_rows(book, p))
    if action == 'save_entry':
        day = parse_day(text(p, 'day'))
        amount = parse_amount(text(p, 'amount'))
        note, category, payment = text(p, 'note'), text(p, 'category', nonempty=True), text(p, 'payment', nonempty=True)
        if p['id'] is None:
            record_id = book.add(day, amount, note, category, payment)
        else:
            record_id = identifier(p)
            book.update(record_id, day, amount, note, category, payment)
        return {'id': str(record_id)}
    if action == 'delete_entry':
        book.delete(identifier(p))
        return {'deleted': True}
    if action == 'summary':
        month = month_text(p)
        summary = book.month_summary(month)
        total = summary['total_units']
        days = monthrange(int(month[:4]), int(month[5:]))[1]
        budget = book.get_budget(month)
        highest = max(summary['by_day'].values(), default=0)
        return dict(month=month, amount=money(total), count=summary['count'], days_in_month=days,
                    daily_average=money((total * 2 + days) // (2 * days)),
                    by_category=[dict(name=name, amount=money(value), percent=round(value * 100 / total, 2))
                                 for name, value in summary['by_category']],
                    by_day=[dict(day=day, amount=money(value), percent=round(value * 100 / highest, 2) if highest else 0)
                            for day, value in summary['by_day'].items()],
                    budget=money(budget) if budget is not None else None,
                    remaining=money(budget - total) if budget is not None else None,
                    over_budget=money(max(total - budget, 0)) if budget is not None else '0.00')
    if action == 'calendar':
        year = p['year']
        if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError('年份必须是1至9999之间的整数。')
        rows = book.list_entries(f'{year:04d}-01-01', f'{year:04d}-12-31')
        months = {f'{year:04d}-{i:02d}': [0, 0] for i in range(1, 13)}
        daily = {}
        for row in rows:
            aggregate = daily.setdefault(row['day'], [0, 0])
            aggregate[0] += row['amount_units']
            aggregate[1] += 1
            months[row['day'][:7]][0] += row['amount_units']
            months[row['day'][:7]][1] += 1
        return dict(year=year, amount=money(sum(r['amount_units'] for r in rows)), count=len(rows),
                    recorded_days=len(daily),
                    months=[dict(month=m, amount=money(v[0]), count=v[1]) for m, v in months.items()],
                    by_day=[dict(day=d, amount=money(v[0]), count=v[1]) for d, v in sorted(daily.items())])
    if action == 'save_budget':
        month = month_text(p)
        amount = parse_amount(text(p, 'amount'))
        if amount == 0:
            raise ValueError('月预算金额必须大于零。')
        book.set_budget(month, amount)
        return {'saved': True}
    if action == 'delete_budget':
        book.clear_budget(month_text(p))
        return {'deleted': True}
    if action == 'products':
        return {'products': [dict(id=str(r['id']), name=r['name'], price=money(r['price_units']))
                             for r in book.list_products()]}
    if action == 'save_product':
        name = text(p, 'name', nonempty=True)
        price = parse_amount(text(p, 'price'))
        if p['id'] is None:
            product_id = book.add_product(name, price)
        else:
            product_id = identifier(p)
            book.update_product(product_id, name, price)
        return {'id': str(product_id)}
    if action == 'delete_product':
        book.delete_product(identifier(p))
        return {'deleted': True}
    if action == 'product_amount':
        product = book.get_product(identifier(p))
        value = text(p, 'quantity')
        if not value.isascii() or not value.isdecimal():
            raise ValueError('数量请输入1～999999之间的正整数。')
        digits = value.lstrip('0')
        if not digits or len(digits) > 6:
            raise ValueError('数量请输入1～999999之间的正整数。')
        quantity = int(digits)
        if type(p['add']) is not bool:
            raise ValueError('add 必须是布尔值。')
        current = parse_amount(text(p, 'current_amount'))
        units = product['price_units'] * quantity + (current if p['add'] else 0)
        # Use the same money parser as desktop to enforce SQLite's exact integer ceiling.
        amount = money(parse_amount(money(units)))
        return dict(amount=amount, description=f"{product['name']} × {quantity}", quantity=quantity)
    raise ValueError(f'不支持的操作：{action}。')


def boundary(directory, operation, callback):
    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if sqlite3.sqlite_version_info < (3, 37, 0):
            raise RuntimeError(f'SQLite {sqlite3.sqlite_version} 不支持账本的 STRICT 约束，至少需要3.37。')
        data = callback(directory)
        return json.dumps({'ok': True, 'data': data}, ensure_ascii=False)
    except Exception as error:
        detail = f'\n[{datetime.now().isoformat()}] {operation}\n{traceback.format_exc()}\n'
        # stderr goes to Android Logcat. A logging failure propagates to Java's visible error boundary.
        print(detail, file=sys.stderr)
        with (directory / 'errors.log').open('a', encoding='utf-8') as stream:
            stream.write(detail)
        return json.dumps({'ok': False, 'error': {'type': type(error).__name__, 'message': str(error)}},
                          ensure_ascii=False)


def handle(data_directory, request_json):
    def run(directory):
        request = json.loads(request_json)
        if not isinstance(request, dict) or set(request) != {'action', 'payload'}:
            raise ValueError('请求必须包含 action 和 payload。')
        if not isinstance(request['action'], str) or not isinstance(request['payload'], dict):
            raise ValueError('action 必须是文本，payload 必须是对象。')
        with closing(Ledger(directory / 'ledger.sqlite3')) as book:
            return dispatch(book, request['action'], request['payload'])
    return boundary(data_directory, 'request', run)


def export_file(data_directory, action, payload_json, destination_path):
    def run(directory):
        destination = Path(destination_path)
        if action == 'logs':
            source = directory / 'errors.log'
            # No errors is a documented empty log state, not a fabricated successful operation.
            content = source.read_text(encoding='utf-8') if source.exists() else '尚无错误日志。\n'
            destination.write_text(content, encoding='utf-8')
            return {'exported': True}
        with closing(Ledger(directory / 'ledger.sqlite3')) as book:
            if action == 'backup':
                book.backup(destination)
            elif action == 'csv':
                payload = json.loads(payload_json)
                if not isinstance(payload, dict):
                    raise ValueError('CSV筛选条件必须是对象。')
                book.export_csv(destination, filtered_rows(book, payload))
            else:
                raise ValueError(f'不支持的导出类型：{action}。')
        return {'exported': True}
    return boundary(data_directory, f'export:{action}', run)


def restore_file(data_directory, source_path):
    def run(directory):
        source = Path(source_path).resolve()
        # Read-only inspection before making any replacement or backup of the active ledger.
        with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True)) as candidate:
            candidate.execute('BEGIN')
            Ledger._check_backup(candidate)
        with closing(Ledger(directory / 'ledger.sqlite3')) as book:
            backups = directory / 'backups'
            backups.mkdir(exist_ok=True)
            book.backup(backups / f'before-restore-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3')
            book.restore(source)
        return {'restored': True}
    return boundary(data_directory, 'restore', run)
