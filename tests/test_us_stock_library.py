from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from research.us_stock_library import parse_holdings, validate_symbol, append_catalog, Downloader
from research.alpaca_pilot import digest


def bar(day='2016-01-04', price='100.1234'):
    return {'t':day+'T05:00:00Z','o':price,'h':'102','l':'99','c':'101','v':'1000.25'}


def response(payload):
    obj=io.BytesIO(json.dumps(payload).encode());obj.status=200
    return obj


class StockLibraryTests(unittest.TestCase):
    def test_issuer_parser_checks_identity_and_retains_exclusions(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'source.xlsx'
            strings=['Ticker Symbol:','SPY','Holdings:','As of 22-Oct-2026','Name','Ticker','Identifier','USD','AAPL','037833100','-','999USDZ92','2602335D','436CVR021']
            cells=[('A1',0),('B1',1),('A2',2),('B2',3),('A3',4),('B3',5),('C3',6),
                   ('A4',8),('B4',8),('C4',9),('H4',7),('B5',10),('C5',11),('H5',7),('B6',12),('C6',13),('H6',7)]
            rows={}
            for ref,index in cells: rows.setdefault(ref[-1],[]).append(f'<c r="{ref}" t="s"><v>{index}</v></c>')
            for n in ('4','5','6'):rows[n].append(f'<c r="G{n}"><v>1</v></c>')
            ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('xl/sharedStrings.xml',f'<sst xmlns="{ns}">'+''.join(f'<si><t>{s}</t></si>' for s in strings)+'</sst>')
                z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{ns}"><sheetData>'+''.join('<row>'+''.join(c)+'</row>' for c in rows.values())+'</sheetData></worksheet>')
            result=parse_holdings(p)
            self.assertEqual([r['symbol'] for r in result['equities']],['AAPL'])
            self.assertEqual(len(result['excluded']),2)
            self.assertEqual(result['holdings_asof'],'2026-10-22')

    def test_full_partial_missing_and_interior_gap(self):
        expected={'2016-01-04','2016-01-05','2016-01-06'}
        rows,q=validate_symbol('AAPL',[bar(d) for d in sorted(expected)],expected)
        self.assertEqual(q['status'],'structural_full_window');self.assertEqual(len(rows),3)
        rows,q=validate_symbol('AAPL',[bar('2016-01-05'),bar('2016-01-06')],expected)
        self.assertEqual(q['status'],'structural_partial_window');self.assertEqual(q['leading_missing_sessions'],1)
        rows,q=validate_symbol('AAPL',[bar('2016-01-04'),bar('2016-01-06')],expected)
        self.assertEqual(rows,[]);self.assertEqual(q['interior_missing_sessions'],['2016-01-05'])
        self.assertEqual(validate_symbol('AAPL',[],expected)[1]['status'],'unavailable')

    def test_corrupt_and_duplicate_bars_rejected(self):
        for raw in [[bar(),bar()],[{**bar(),'o':'NaN'}],[{**bar(),'h':'50'}],[{**bar(),'t':'2016-01-04T06:00:00Z'}]]:
            with self.assertRaises(ValueError):validate_symbol('AAPL',raw,{'2016-01-04'})

    def test_incremental_native_catalog_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'catalog';root.mkdir()
            for symbol in ['AAPL','BRK.B']:
                rows,_=validate_symbol(symbol,[bar()],{'2016-01-04'})
                self.assertEqual(append_catalog(rows,root),1)
            before={str(p):digest(p) for p in root.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                append_catalog(rows,root)
            self.assertEqual(before,{str(p):digest(p) for p in root.rglob('*') if p.is_file()})
            from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
            cat=ParquetDataCatalog(str(root.resolve()))
            self.assertEqual(len(cat.bars()),2)
            self.assertEqual(len(cat.instruments()),2)

    def test_pagination_budget_and_redacted_requests(self):
        with tempfile.TemporaryDirectory() as t, patch('research.us_stock_library.time.sleep'):
            d=Downloader(Path(t)/'raw',('secret-key','secret-value'),'2026-10-22')
            with patch.object(d.opener,'open') as opened:
                opened.side_effect=[response({'bars':{'AAPL':[bar()]},'next_page_token':'next'}),response({'bars':{},'next_page_token':None})]
                self.assertEqual(len(d.batch(['AAPL'],1)['AAPL']),1)
                self.assertEqual(d.count,2)
            text=(d.root/'requests.json').read_text()
            self.assertNotIn('secret-key',text);self.assertNotIn('secret-value',text)
        with tempfile.TemporaryDirectory() as t:
            d=Downloader(Path(t)/'raw',('k','s'),'2026-10-22',request_limit=0)
            with patch.object(d.opener,'open') as opened:
                with self.assertRaisesRegex(ValueError,'bound'):d.batch(['AAPL'],1)
                opened.assert_not_called()


if __name__=='__main__':unittest.main()
