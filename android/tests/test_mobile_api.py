import csv
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from mobile_api import handle, export_file, restore_file
from ledger import Ledger


class MobileApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / 'phone'

    def response(self, action, **payload):
        return json.loads(handle(str(self.directory), json.dumps({'action': action, 'payload': payload})))

    def call(self, action, **payload):
        result = self.response(action, **payload)
        self.assertTrue(result['ok'], result)
        return result['data']

    def save(self, amount='33.662720', **extra):
        payload = dict(id=None, day='2026-10-11', amount=amount, note='午餐 <script> / 中文',
                       category='餐饮', payment='微信')
        payload.update(extra)
        return self.call('save_entry', **payload)['id']

    def entries(self, **extra):
        payload = dict(start_day=None, end_day=None, category=None, payment=None, keyword='')
        payload.update(extra)
        return self.call('entries', **payload)

    def test_blank_start_six_decimals_and_reopen(self):
        initial = self.call('bootstrap', today='2026-10-11')
        self.assertEqual(initial['month_count'], 0)
        self.assertEqual(initial['today_amount'], '0.00')
        record = self.save()
        self.assertIsInstance(record, str)
        self.assertEqual(self.entries()['entries'][0]['amount'], '33.66272')
        self.assertEqual(self.call('bootstrap', today='2026-10-11')['month_amount'], '33.66272')
        with closing(sqlite3.connect(self.directory / 'ledger.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT amount_units FROM expenses').fetchone()[0], 33662720)

    def test_large_money_and_record_id_never_cross_json_as_number(self):
        self.save('9223372036854.775807')
        with closing(sqlite3.connect(self.directory / 'ledger.sqlite3')) as db:
            db.execute('UPDATE expenses SET id = 9007199254740993')
            db.commit()
        row = self.entries()['entries'][0]
        self.assertEqual(row['id'], '9007199254740993')
        self.assertEqual(row['amount'], '9223372036854.775807')
        self.save('0', id=row['id'])
        self.assertEqual(self.entries()['amount'], '0.00')
        self.call('delete_entry', id=row['id'])
        self.assertEqual(self.entries()['count'], 0)

    def test_invalid_inputs_do_not_write_and_missing_id_fails(self):
        self.call('bootstrap', today='2026-10-11')
        for field, invalid in [('amount', 'NaN'), ('amount', '0.0000001'), ('amount', 0.1),
                               ('day', '2026-02-30'), ('category', ''), ('payment', None)]:
            with self.subTest(field=field, invalid=invalid):
                data = dict(id=None, day='2026-10-11', amount='1', note='', category='餐饮', payment='微信')
                data[field] = invalid
                self.assertFalse(self.response('save_entry', **data)['ok'])
        self.assertFalse(self.response('delete_entry', id='999')['ok'])
        self.assertFalse(self.response('delete_entry', id=1)['ok'])
        self.assertFalse(self.response('not_supported')['ok'])
        self.assertEqual(self.entries()['count'], 0)
        self.assertIn('Traceback', (self.directory / 'errors.log').read_text(encoding='utf-8'))

    def test_filters_calendar_zero_days_and_exact_summary_budget(self):
        self.save('0', day='2026-10-10')
        self.save('0.000001')
        self.save('1.2', category='购物', payment='现金')
        self.save('7', day='2026-09-11')
        self.assertEqual(self.entries(keyword='购物')['amount'], '1.20')
        self.assertEqual(self.entries(start_day='2026-10-01', end_day='2026-10-31')['count'], 3)
        self.call('save_budget', month='2026-10', amount='1')
        summary = self.call('summary', month='2026-10')
        self.assertEqual(summary['amount'], '1.200001')
        self.assertEqual(summary['remaining'], '-0.200001')
        self.assertEqual(summary['over_budget'], '0.200001')
        self.assertEqual(summary['daily_average'], '0.03871')
        self.assertEqual(summary['by_day'][1]['percent'], 100)
        year = self.call('calendar', year=2026)
        self.assertEqual(year['recorded_days'], 3)
        self.assertEqual(len(year['months']), 12)
        self.assertEqual(next(d for d in year['by_day'] if d['day'] == '2026-10-10')['amount'], '0.00')
        self.assertEqual(year['months'][9]['count'], 3)
        self.call('delete_budget', month='2026-10')
        self.assertIsNone(self.call('summary', month='2026-10')['budget'])
        self.assertFalse(self.response('save_budget', month='2026-10', amount='0')['ok'])

    def test_products_precise_subtotal_and_history_unchanged(self):
        product = self.call('save_product', id=None, name=' 饮料 ', price='1.000001')['id']
        subtotal = self.call('product_amount', id=product, quantity='3', current_amount='0.000001', add=True)
        self.assertEqual(subtotal['amount'], '3.000004')
        self.assertEqual(subtotal['description'], '饮料 × 3')
        self.save(subtotal['amount'])
        self.assertFalse(self.response('save_product', id=None, name='饮料', price='2')['ok'])
        for qty in ['0', '1000000', '-1', '1.5', '３']:
            self.assertFalse(self.response('product_amount', id=product, quantity=qty, current_amount='0', add=False)['ok'])
        self.call('delete_product', id=product)
        self.assertEqual(self.entries()['amount'], '3.000004')
        self.assertEqual(self.call('products')['products'], [])

    def test_backup_csv_and_desktop_compatible_restore(self):
        record = self.save(note='=1+2')
        self.call('save_product', id=None, name='商品', price='0.000001')
        self.call('save_budget', month='2026-10', amount='100')
        backup = Path(self.temp.name) / 'export.sqlite3'
        result = json.loads(export_file(str(self.directory), 'backup', '{}', str(backup)))
        self.assertTrue(result['ok'], result)
        with self.subTest('desktop accepts backup'):
            desktop = Ledger(backup)
            self.addCleanup(desktop.close)
            self.assertEqual(desktop.list_entries()[0]['amount_units'], 33662720)
        out = Path(self.temp.name) / 'rows.csv'
        filters = dict(start_day=None, end_day=None, category=None, payment=None, keyword='')
        self.assertTrue(json.loads(export_file(str(self.directory), 'csv', json.dumps(filters), str(out)))['ok'])
        with out.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[1][1], '33.66272')
        self.assertEqual(rows[1][4], "'=1+2")
        self.call('delete_entry', id=record)
        restored = json.loads(restore_file(str(self.directory), str(backup)))
        self.assertTrue(restored['ok'], restored)
        self.assertEqual(self.entries()['amount'], '33.66272')
        self.assertEqual(len(list((self.directory / 'backups').glob('before-restore-*.sqlite3'))), 1)

    def test_bad_restore_preserves_current_data_and_reports_error(self):
        self.save('2.2')
        invalid = Path(self.temp.name) / 'bad.sqlite3'
        invalid.write_text('not a database', encoding='utf-8')
        result = json.loads(restore_file(str(self.directory), str(invalid)))
        self.assertFalse(result['ok'])
        self.assertEqual(self.entries()['amount'], '2.20')

    def test_unknown_schema_never_returns_success(self):
        self.save('1')
        with closing(sqlite3.connect(self.directory / 'ledger.sqlite3')) as db:
            db.execute("CREATE TRIGGER deny_insert BEFORE INSERT ON expenses BEGIN SELECT RAISE(ABORT, 'blocked'); END")
            db.commit()
        result = self.response('save_entry', id=None, day='2026-10-11', amount='2', note='', category='餐饮', payment='微信')
        self.assertFalse(result['ok'])
        with closing(sqlite3.connect(self.directory / 'ledger.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM expenses').fetchone()[0], 1)

    def test_read_only_sqlite_write_fails_visibly(self):
        self.save('1')
        connect = sqlite3.connect
        def read_only(path):
            return connect(f'{Path(path).as_uri()}?mode=ro', uri=True)
        with patch('ledger.sqlite3.connect', side_effect=read_only):
            result = self.response('save_entry', id=None, day='2026-10-11', amount='2', note='', category='餐饮', payment='微信')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['type'], 'OperationalError')
        self.assertIn('readonly', result['error']['message'])
        self.assertEqual(self.entries()['count'], 1)


if __name__ == '__main__':
    unittest.main()
