"""Parse preserved official issuer distributions without spreadsheet dependencies."""
from decimal import Decimal
from html.parser import HTMLParser
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import pandas as pd

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def ssga_spy(path):
    with zipfile.ZipFile(path) as book:
        strings = [''.join(element.itertext()) for element in
                   ET.fromstring(book.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        sheet = ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
    result = []
    for row in sheet.findall('.//s:sheetData/s:row', NS):
        values = {}
        for cell in row.findall('s:c', NS):
            column = ''.join(ch for ch in cell.get('r') if ch.isalpha())
            value = cell.find('s:v', NS)
            text = value.text if value is not None else ''
            values[column] = strings[int(text)] if cell.get('t') == 's' and text else text
        if values.get('B') != 'SPY':
            continue
        if values.get('C') != '78462F103':
            raise ValueError('Unexpected SPY identity.')
        amount = sum((Decimal(values.get(key, '').strip() or '0') for key in ('G', 'H', 'I')), Decimal(0))
        result.append(dict(symbol='SPY', ex_date=pd.to_datetime(values['D'], format='%m/%d/%Y').strftime('%Y-%m-%d'),
                           pay_date=pd.to_datetime(values['F'], format='%m/%d/%Y').strftime('%Y-%m-%d'), amount=str(amount)))
    return validate(result)


def ishares_ief(path):
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.rows = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            raw = values.get('componentprops')
            if tag == 'walrus-render-on-client' and raw and raw.startswith('{'):
                value = json.loads(raw)
                if 'distributionTableData' in value:
                    self.rows.append(value['distributionTableData'])
    parser = Parser()
    parser.feed(Path(path).read_text())
    if len(parser.rows) != 1:
        raise ValueError('Expected one embedded issuer distribution table.')
    columns = {row['name']: row['value'] for row in parser.rows[0]}
    if not len(columns['exDate']) == len(columns['payableDate']) == len(columns['totalDistribution']):
        raise ValueError('Unequal issuer date/amount coverage.')
    records = []
    for ex, pay, amount in zip(columns['exDate'], columns['payableDate'], columns['totalDistribution'], strict=True):
        records.append(dict(symbol='IEF', ex_date=pd.to_datetime(str(ex), format='%Y%m%d').strftime('%Y-%m-%d'),
                            pay_date=pd.to_datetime(str(pay), format='%Y%m%d').strftime('%Y-%m-%d'), amount=str(Decimal(str(amount)))))
    return validate(records)


def validate(rows):
    if not rows:
        raise ValueError('Missing issuer distribution rows.')
    ids = set()
    for row in rows:
        key = row['symbol']+'-'+row['ex_date']
        if (key in ids or not Decimal(row['amount']).is_finite() or Decimal(row['amount']) <= 0 or
                pd.Timestamp(row['pay_date']) < pd.Timestamp(row['ex_date'])):
            raise ValueError('Invalid/duplicate action or payment before entitlement.')
        ids.add(key)
        row['id'] = key
    return sorted(rows, key=lambda row: (row['ex_date'], row['symbol']))
