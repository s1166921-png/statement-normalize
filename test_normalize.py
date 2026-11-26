import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from normalize import convert

HEADER = 'date,currency,amount,kind,provider_id,settlement_id\n'

class Tests(unittest.TestCase):
    def parse(self, data, **kwargs):
        return convert(io.StringIO(HEADER + data), **kwargs)

    def test_preserves_sign_currency_and_original_rows(self):
        receipts, audit = self.parse('30/11/2026,eur,"1.234,56",credit,TX-1,\n30/11/2026,EUR,"-5,20",fee,TX-1,\n30/11/2026,USD,"-18,00",debit,TX-2,\n', day_format='%d/%m/%Y', decimal=',')
        self.assertEqual(audit['net_by_currency'], {'EUR': '1229.36', 'USD': '-18.00'})
        self.assertEqual(audit['rows'][0]['original']['amount'], '1.234,56')
        self.assertEqual(audit['rows'][1]['source_line'], 3)
        self.assertEqual(receipts, [{'date':'2026-11-30','currency':'EUR','amount':'1234.56','settlement_id':''}])

    def test_trusted_reference_requires_explicit_opt_in(self):
        row = '2026-11-30,EUR,12,credit,PROVIDER-7,SETTLEMENT-B\n'
        self.assertEqual(self.parse(row)[0][0]['settlement_id'], '')
        self.assertEqual(self.parse(row, trusted=True)[0][0]['settlement_id'], 'SETTLEMENT-B')

    def test_flat_and_compact_do_not_double_count_fee(self):
        flat = self.parse('2026-11-30,EUR,100,credit,P,\n2026-11-30,EUR,-3,fee,P,\n')
        compact = self.parse('2026-11-30,EUR,97,credit,P,\n')
        self.assertEqual(flat[1]['net_by_currency'], compact[1]['net_by_currency'])
        self.assertEqual(flat[0][0]['amount'], '100')
        self.assertEqual(compact[0][0]['amount'], '97')

    def test_rejects_malformed_rows_and_wrong_sign(self):
        for bad in ('2026-02-30,EUR,1,credit,P,', '2026-11-30,EUR,-1,credit,P,',
                    '2026-11-30,EUR,1,fee,P,', '2026-11-30,EUR,1e3,credit,P,',
                    '2026-11-30,EUR,1,credit,P,,extra', '2026-11-30,EUR,1,credit,P',
                    '2026-11-30,EU€,1,credit,P,', '2026-11-30,EUR,"12,34.56",credit,P,'):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'line 2'):
                self.parse(bad + '\n')

    def test_blank_header_repeat_and_no_rows(self):
        for content in ('', HEADER.replace('provider_id','kind'), HEADER):
            with self.subTest(content=content), self.assertRaises(ValueError):
                convert(io.StringIO(content))

    def test_repeated_credit_rows_are_not_silently_dropped(self):
        row = '2026-11-30,EUR,12,credit,PROVIDER-7,\n'
        receipts, audit = self.parse(row + row.replace(",12,", ",12.00,"))
        self.assertEqual(len(receipts), 2)
        self.assertEqual(audit['repeated_row_lines'], [3])

    def test_multiline_field_keeps_correct_start_line(self):
        _, audit = self.parse('2026-11-30,EUR,1,credit,"P\n1",\n2026-11-30,EUR,-1,fee,P,\n')
        self.assertEqual([x['source_line'] for x in audit['rows']], [2,4])

    def test_exact_sum_beyond_decimal_default_context(self):
        _, audit = self.parse('2026-11-30,EUR,99999999999999999999999999.99,credit,P,\n2026-11-30,EUR,0.01,credit,Q,\n')
        self.assertEqual(audit['net_by_currency']['EUR'], '100000000000000000000000000.00')

    def test_cli_refuses_partial_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as td:
            src, out = Path(td)/'src.csv', Path(td)/'out'
            cmd = [sys.executable, 'normalize.py', str(src), str(out)]
            src.write_text(HEADER + '2026-11-30,EUR,12,credit,P,\nbroken\n', encoding='utf8')
            result = subprocess.run(cmd, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())
            src.write_text(HEADER + '2026-11-30,EUR,12,credit,P,\n', encoding='utf8')
            subprocess.run(cmd, check=True)
            with (out/'receipts.csv').open() as f:
                self.assertEqual(list(csv.DictReader(f))[0]['amount'], '12')
            self.assertEqual(json.loads((out/'audit.json').read_text())['net_by_currency'], {'EUR':'12'})
            before = (out/'receipts.csv').read_bytes()
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)
            self.assertEqual((out/'receipts.csv').read_bytes(), before)
