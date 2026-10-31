import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nautilus_trader.model.data import Bar, QuoteTick
from nautilus_trader.model.objects import Price, Quantity
from research.spy_backtest import BAR_TYPE, INSTRUMENT_ID
from paper_trading.alpaca import AlpacaPaperHTTP, check_quote, validate_order, PaperError
from paper_trading.alpaca_native import Context, started_node, stop_node


from paper_trading.alpaca_fixture import native_fixture
from scripts.alpaca_paper import history_bars, unresolved_journals, session
from zoneinfo import ZoneInfo


class PaperPolicyTests(unittest.TestCase):
    def test_warmup_coverage_and_unresolved_journal_gate(self):
        base = datetime(2026,1,1,tzinfo=ZoneInfo('America/New_York'))
        calendar, bars = [], []
        for i in range(201):
            stamp = base + timedelta(days=i)
            calendar.append({'date':stamp.date().isoformat()})
            bars.append({'t':stamp.astimezone(timezone.utc).isoformat(),'o':100,'h':101,'l':99,'c':100,'v':1000})
        payload = {'bars':bars,'next_page_token':None}
        self.assertEqual(len(history_bars(payload,calendar,'2026-12-01')),201)
        with self.assertRaises(PaperError):
            history_bars({'bars':bars[:-1]},calendar,'2026-12-01')
        with self.assertRaises(PaperError):
            history_bars({**payload,'next_page_token':'more'},calendar,'2026-12-01')
        with tempfile.TemporaryDirectory() as t, patch('scripts.alpaca_paper.RUNS',Path(t)):
            folder=Path(t)/'old-session';folder.mkdir()
            p=folder/'journal.json';p.write_text('[{"status":"unknown_submission"}]')
            self.assertEqual(unresolved_journals(),[str(p)])
            p.write_text('[{"status":"filled"}]')
            self.assertEqual(unresolved_journals(),[])

    def test_transport_cannot_route_to_live_or_send_oversized_order(self):
        with patch('paper_trading.alpaca.credentials', return_value=('fake','fake')):
            client = AlpacaPaperHTTP()
        with patch.object(client.opener, 'open') as opened:
            for method, path, body, data in [
                ('GET','https://api.alpaca.markets/v2/account',None,False),
                ('POST','/v2/orders',{'symbol':'SPY','qty':'200'},False),
                ('POST','/v2/orders',{},True),
                ('DELETE','/v2/orders',None,False),
                ('GET','/v2/stocks/AAPL/quotes/latest',None,True)]:
                with self.assertRaises(PaperError):
                    client.request(method,path,body,data=data)
            opened.assert_not_called()

    def test_order_bound_no_short_or_pyramid(self):
        body = {"symbol": "SPY", "qty": "1", "side": "buy", "type": "limit",
                "limit_price": "500", "time_in_force": "day", "extended_hours": False}
        validate_order(body, Decimal(0))
        for change, position in [({"qty": "2"}, 0), ({"side": "sell"}, 0), ({}, 1),
                                  ({"limit_price": "1001"}, 0), ({"limit_price": "NaN"}, 0),
                                  ({"symbol": "AAPL"}, 0), ({"extended_hours": True}, 0)]:
            with self.subTest(change=change), self.assertRaises(PaperError):
                validate_order({**body, **change}, Decimal(position))

    def test_quote_freshness_and_crossed_market(self):
        q = {"t": "2026-10-26T13:30:00Z", "bp": 100, "ap": 100.01}
        now = int(datetime(2026, 10, 26, 13, 30, 2, tzinfo=timezone.utc).timestamp()) * 1_000_000_000
        check_quote(q, now)
        for bad, stamp in [({**q, "bp": 101}, now), (q, now + 11_000_000_000), (q, now - 3_000_000_000)]:
            with self.assertRaises(PaperError):
                check_quote(bad, stamp)


class NativeIntegrationTests(unittest.TestCase):
    def test_fractional_partial_fill_halts_for_reconciliation(self):
        with tempfile.TemporaryDirectory() as t:
            result=asyncio.run(native_fixture(t, partial=True))
            self.assertTrue(result['unknown'])
            self.assertEqual(result['broker_post_count'],1)
            self.assertEqual(result['native_fills'],0)
            self.assertEqual(json.loads((Path(t)/'journal.json').read_text())[0]['status'],'reconciliation_required')

    def test_complete_session_orchestration_with_fake_broker(self):
        class API:
            def __init__(self):
                self.qty=0
                self.posts=0
                self.clock={'is_open':True,'timestamp':'2026-10-26T09:30:05-04:00'}
                base=datetime(2026,10,26,tzinfo=ZoneInfo('America/New_York'))-timedelta(days=251)
                self.calendar=[];self.bars=[]
                for i in range(250):
                    stamp=base+timedelta(days=i)
                    self.calendar.append({'date':stamp.date().isoformat()})
                    self.bars.append({'t':stamp.astimezone(timezone.utc).isoformat(),
                        'o':100+i/10,'h':100+i/10,'l':100+i/10,'c':100+i/10,'v':100})
            def request(self,method,path,body=None,**kwargs):
                if path.startswith('/v2/calendar'):return self.calendar
                if path.startswith('/v2/stocks/SPY/bars'):return {'bars':self.bars}
                if path.startswith('/v2/stocks/SPY/quotes'):
                    return {'quote':{'t':datetime.now(timezone.utc).isoformat(),'bp':99.99,'ap':100}}
                if path=='/v2/clock':return self.clock
                if path=='/v2/positions':return [{'symbol':'SPY','qty':str(self.qty)}] if self.qty else []
                if path.startswith('/v2/orders?'):return []
                if method=='POST':
                    self.posts+=1;self.qty=1
                    return {'id':'fake-session-1','client_order_id':body['client_order_id'],
                        'symbol':'SPY','side':'buy','status':'filled','filled_qty':'1','filled_avg_price':'100.0001'}
                raise AssertionError((method,path))
        with tempfile.TemporaryDirectory() as t, patch('scripts.alpaca_paper.RUNS',Path(t)):
            api=API()
            result=asyncio.run(session(api,{'clock':api.clock,'cash':'100000'},Path(t)/'current'))
            self.assertEqual(result['status'],'paper_observed')
            self.assertTrue(result['native_broker_position_match'])
            self.assertEqual(api.posts,1)
            self.assertEqual(result['native_fills'],1)

    def test_saved_spy_signal_replay(self):
        with tempfile.TemporaryDirectory() as t:
            r = asyncio.run(native_fixture(t, saved_spy=True))
            self.assertEqual(r['native_fills'],2)
            self.assertEqual(r['signal_input'],'saved_SPY_250_bars_to_2019_end_then_2020Q1')
            self.assertEqual(len(r['source_data_sha256']),64)

    def test_native_ema_order_fill_exit_and_duplicate_quote(self):
        with tempfile.TemporaryDirectory() as t:
            r = asyncio.run(native_fixture(t))
            self.assertEqual(r["broker_post_count"], 2)
            self.assertEqual(r["native_fills"], 2)
            self.assertEqual(Decimal(r["ending_native_position"]), 0)

    def test_unknown_submission_is_not_retried(self):
        with tempfile.TemporaryDirectory() as t:
            r = asyncio.run(native_fixture(t, timeout=True))
            self.assertTrue(r["unknown"])
            self.assertEqual(r["broker_post_count"], 1)
            self.assertEqual(json.loads((Path(t) / "journal.json").read_text())[0]["status"], "unknown_submission")

    def test_closed_market_never_posts(self):
        with tempfile.TemporaryDirectory() as t:
            r = asyncio.run(native_fixture(t, closed=True))
            self.assertEqual(r["broker_post_count"], 0)


if __name__ == "__main__":
    unittest.main()
