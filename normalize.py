"""Offline signed statement normalizer."""
import argparse
import csv
from datetime import datetime
from decimal import Decimal, localcontext
import json
from pathlib import Path
import re
import sys

REQUIRED = ('date', 'currency', 'amount', 'kind', 'provider_id')
RECEIPT_FIELDS = ('date', 'currency', 'amount', 'settlement_id')
DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y')


def amount_from(raw, decimal):
    group = ',' if decimal == '.' else '.'
    g, d = re.escape(group), re.escape(decimal)
    if len(raw) > 100 or not re.fullmatch(
            fr'[+-]?(?:[0-9]+|[0-9]{{1,3}}(?:{g}[0-9]{{3}})+)(?:{d}[0-9]+)?', raw):
        raise ValueError('invalid amount for configured decimal mark')
    return Decimal(raw.replace(group, '').replace(decimal, '.'))


def convert(stream, *, day_format=DATE_FORMATS[0], decimal='.', trusted=False, delimiter=','):
    reader = csv.reader(stream, delimiter=delimiter, strict=True)
    try:
        header = next(reader, [])
        if (not set(REQUIRED).issubset(header) or len(header) != len(set(header))
                or any(not item for item in header)):
            raise ValueError('expected distinct columns: ' + ','.join(REQUIRED))
        receipts, rows, totals, seen, repeated = [], [], {}, set(), []
        with localcontext() as ctx:
            ctx.prec = 220  # Up to 100 input characters, including integer and fractional digits.
            while True:
                line = reader.line_num + 1
                cells = next(reader, None)
                if cells is None:
                    break
                if not cells:
                    continue
                if len(cells) != len(header):
                    raise ValueError(f'line {line}: wrong number of columns')
                original = dict(zip(header, cells))
                row = {k: v.strip() for k, v in original.items()}
                try:
                    day = datetime.strptime(row['date'], day_format).date()
                    if day.strftime(day_format) != row['date']:
                        raise ValueError('date must match the configured format exactly')
                    currency = row['currency'].upper()
                    if not re.fullmatch('[A-Z]{3}', currency) or not row['currency'].isascii():
                        raise ValueError('expected a three-letter currency code')
                    amount = amount_from(row['amount'], decimal)
                    kind = row['kind'].lower()
                    if not ((kind == 'credit' and amount > 0)
                            or (kind in ('fee', 'debit') and amount < 0)):
                        raise ValueError('expected positive credit or negative fee/debit')
                except ValueError as exc:
                    raise ValueError(f'line {line}: {exc}') from exc
                normalized = {'date': day.isoformat(), 'currency': currency,
                              'amount': format(amount, 'f')}
                record_key = (normalized['date'], currency, amount, kind, row['provider_id'], row.get('settlement_id', ''))
                if record_key in seen:
                    repeated.append(line)
                seen.add(record_key)
                totals[currency] = totals.get(currency, Decimal(0)) + amount
                rows.append({'source_line': line, **normalized, 'kind': kind,
                             'provider_id': row['provider_id'], 'original': original,
                             'receipt_row': len(receipts) + 2 if kind == 'credit' else None})
                if kind == 'credit':
                    receipts.append({**normalized,
                                     'settlement_id': row.get('settlement_id', '') if trusted else ''})
        if not rows:
            raise ValueError('statement has no data rows')
    except csv.Error as exc:
        raise ValueError(f'near line {reader.line_num}: malformed CSV ({exc})') from exc
    return receipts, {
        'input_rows': len(rows), 'receipt_count': len(receipts), 'rows': rows,
        'net_by_currency': {key: format(value, 'f') for key, value in sorted(totals.items())},
        'repeated_row_lines': repeated,
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('statement', type=Path)
    cli.add_argument('output_dir', type=Path, help='must not already exist')
    cli.add_argument('--decimal', choices=('.', ','), default='.')
    cli.add_argument('--date-format', choices=DATE_FORMATS, default=DATE_FORMATS[0])
    cli.add_argument('--delimiter', choices=(',', ';', 'tab'), default=',')
    cli.add_argument('--trust-settlement-id', action='store_true',
                     help='copy settlement_id only if you verified the platform IDs before running')
    args = cli.parse_args(argv)
    opened_dir = False
    completed = False
    try:
        with args.statement.open(encoding='utf-8-sig', newline='') as source:
            receipts, audit = convert(source, day_format=args.date_format, decimal=args.decimal,
                                      trusted=args.trust_settlement_id,
                                      delimiter='\t' if args.delimiter == 'tab' else args.delimiter)
        args.output_dir.mkdir()
        opened_dir = True
        with (args.output_dir / 'audit.json').open('x', encoding='utf-8') as target:
            json.dump(audit, target, ensure_ascii=False, indent=2)
            target.write('\n')
        with (args.output_dir / 'receipts.csv').open('x', encoding='utf-8', newline='') as target:
            writer = csv.DictWriter(target, RECEIPT_FIELDS)
            writer.writeheader()
            writer.writerows(receipts)
        completed = True
    except (OSError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2
    finally:
        if opened_dir and not completed:
            for name in ('receipts.csv', 'audit.json'):
                (args.output_dir / name).unlink(missing_ok=True)
            args.output_dir.rmdir()
    print(f"{audit['input_rows']} rows, {audit['receipt_count']} credits, "
          f"{len(audit['repeated_row_lines'])} repeated rows. See audit.json.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
