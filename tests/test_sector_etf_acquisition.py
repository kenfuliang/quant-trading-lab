"""Offline transport and preservation tests; no provider requests or simulations."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from research import sector_etf_acquisition as m

class Response:
    status=200
    headers={'Content-Type':'application/json'}
    def __init__(self,payload):self.body=io.BytesIO(payload if isinstance(payload,bytes) else json.dumps(payload).encode())
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,n):return self.body.read(n)

class Opener:
    def __init__(self,responses):self.responses=list(responses);self.requests=[]
    def open(self,request,timeout):
        self.requests.append(request)
        value=self.responses.pop(0)
        if isinstance(value,Exception):raise value
        return Response(value)

class TestSectorAcquisition(unittest.TestCase):
    def make(self,path,responses):
        op=Opener(responses)
        return m.BoundedDownload(path,('TEST_KEY','TEST_SECRET'),opener=op),op

    def test_pagination_preserves_raw_and_only_data_api(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[{'bars':{},'next_page_token':'next'},{'bars':{},'next_page_token':None}])
            with patch.object(m.time,'sleep'):self.assertEqual(len(obj.pages('bars')),2)
            self.assertEqual(len(list(obj.directory.glob('response*'))),2)
            self.assertTrue(all(q.full_url.startswith(m.API['bars']+'?') for q in op.requests))
            journal=(obj.directory/'requests.json').read_text()
            self.assertNotIn('TEST_SECRET',journal);self.assertNotIn('TEST_KEY',journal)
            self.assertNotIn('page_token=',journal)

    def test_document_never_gets_auth_headers(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[b'official terms'])
            obj.document('terms')
            self.assertFalse(any('apca' in k.lower() for k in op.requests[0].headers))

    def test_unknown_endpoint_refused_without_request(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[])
            for k in ['orders','account','https://bad.test','terms']:
                with self.assertRaises(ValueError):obj.get(k)
            self.assertEqual(op.requests,[])

    def test_http_failure_retains_body_without_leaking(self):
        with tempfile.TemporaryDirectory() as d:
            err=urllib.error.HTTPError('sensitive-url',403,'sensitive-message',{},io.BytesIO(b'private-server-error'))
            obj,op=self.make(Path(d)/'raw',[err])
            with self.assertRaisesRegex(ValueError,'private response retained') as caught:obj.get('actions')
            self.assertNotIn('sensitive',str(caught.exception))
            self.assertEqual((obj.directory/'error-01.bin').read_bytes(),b'private-server-error')
            self.assertEqual(obj.records[0]['http_status'],403)

    def test_request_and_time_caps_stop_before_launch(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[])
            with patch.object(m,'REQUEST_CAP',0):
                with self.assertRaises(ValueError):obj.get('bars')
            with patch.object(m.time,'monotonic',return_value=obj.started+601):
                with self.assertRaises(ValueError):obj.get('bars')
            self.assertEqual(op.requests,[])

    def test_oversized_body_is_preserved_and_stopped(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[b'12345'])
            with patch.object(m,'PAGE_CAP',4):
                with self.assertRaises(ValueError):obj.get('bars')
            self.assertEqual((obj.directory/'response-01.bin').read_bytes(),b'12345')
            self.assertEqual(obj.records[0]['status'],'failed')

    def test_repeated_token_stops_not_retry(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[{'corporate_actions':{},'next_page_token':'same'}]*2)
            with patch.object(m.time,'sleep'):
                with self.assertRaisesRegex(ValueError,'Repeated'):obj.pages('actions')
            self.assertEqual(len(op.requests),2)

    def test_malformed_payload_is_retained(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[{'corporate_actions':[]}])
            with self.assertRaisesRegex(ValueError,'schema'):obj.pages('actions')
            self.assertTrue((obj.directory/'response-01.bin').exists())

    def test_existing_output_is_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            obj,op=self.make(Path(d)/'raw',[])
            with self.assertRaises(FileExistsError):self.make(Path(d)/'raw',[])

    def test_redirect_never_forwards_auth(self):
        from research.alpaca_pilot import NoRedirect
        with self.assertRaises(ValueError):NoRedirect().redirect_request(None,None,302,'redirect',{},'https://bad.test')
