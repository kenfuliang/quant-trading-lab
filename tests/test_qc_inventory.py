import copy
import unittest
from research.qc_inventory import classify,normalize_community,tutorial_article_observed,tutorial_index

class CatalogEvidenceTests(unittest.TestCase):
    def test_rows_are_not_unique_strategy_counts(self):
        pages=[]
        for page in range(1,109):
            rows=[]
            for i in range((page-1)*5+1,page*5+1):
                sid=1 if i==540 else i
                rows.append({'cells':['Name'+str(sid),'Author','Org','-','0.00','-','Clone'],'links':[{'href':f'/strategies/{sid}/','title':'Name'+str(sid)}]})
            pages.append({'page':page,'captured_utc':'fixed','rows':rows})
        records,n=normalize_community({'first':pages})
        self.assertEqual(n,540);self.assertEqual(len(records),539)
        fixed=copy.deepcopy(pages);fixed[-1]['rows'][-1]={'cells':['Name540','Author','Org','-','0.00','-','Clone'],'links':[{'href':'/strategies/540/','title':'Name540'}]}
        records,n=normalize_community({'first':pages,'repair':fixed})
        self.assertEqual(len(records),540);self.assertEqual(n,1080)
        self.assertIsNone(records[0]['observed_claims'][0]['oos_3m_return'])
        self.assertEqual(records[0]['observed_claims'][0]['oos_3m_sharpe'],'0.00')

    def test_conflicting_identity_is_not_silently_merged(self):
        p=[{'page':i,'captured_utc':'fixed','rows':[{'cells':['A','B','C','-','-','-','Clone'],'links':[{'href':f'/strategies/{i*5+j}/','title':'A'}]} for j in range(5)]} for i in range(1,109)]
        q=copy.deepcopy(p);q[0]['rows'][0]['links'][0]['title']='Changed'
        with self.assertRaises(ValueError):normalize_community({'p':p,'q':q})

    def test_opaque_names_and_horizons_do_not_invent_economic_family(self):
        self.assertEqual(classify('The Kinetic Titan')['families'],['unresolved'])
        self.assertEqual(classify('Intraday')['families'],['unresolved'])
        self.assertNotIn('options',classify('VIX Risk Rotation')['families'])
        self.assertIn('options',classify('Systematic short puts')['families'])
        result=classify('ETF momentum with mean reversion')
        self.assertIn('momentum',result['families']);self.assertIn('mean_reversion',result['families'])
        self.assertFalse(result['economic_mechanism_verified'])

    def test_soft404_is_not_accessible_article(self):
        self.assertFalse(tutorial_article_observed({'status':200,'final_url':'https://www.quantconnect.com/404','headings':[]}))
        self.assertFalse(tutorial_article_observed({'status':200,'final_url':'https://www.quantconnect.com/research/123/x/','headings':[]}))
        self.assertTrue(tutorial_article_observed({'status':200,'final_url':'https://www.quantconnect.com/research/123/x/','headings':['X']}))

    def test_index_extracts_strategy_links_not_navigation(self):
        rows=tutorial_index('<nav><a href="/docs">Docs</a></nav><table><tr><td><a href="/tutorials/strategy-library/x">X</a></td><td>Momentum</td></tr></table>')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['title'],'X');self.assertIn('Momentum',rows[0]['description'])
