"""Display truncation and wrong-identity rejection for the result reader."""
import unittest
from reporting.soxl_review import number, observed_case

class SoxlReviewTests(unittest.TestCase):
    def test_truncation_never_becomes_a_number(self):
        self.assertIsNone(number('"longest_uw_days":52...', 'longest_uw_days'))
        self.assertEqual(number('"longest_uw_days":529,', 'longest_uw_days'), 529)
        self.assertIsNone(number('"dd":-0.49...', 'dd'))

    def test_wrong_run_is_not_a_result(self):
        with self.assertRaisesRegex(ValueError,'run statistics'):
            observed_case('container result-tab-statistics-other', 'candidate', 'expected')

    def test_native_zero_drawdown_remains_undefined(self):
        text='container result-tab-statistics-abc\n'
        for i,(k,v) in enumerate((('Compounding Annual Return','10%'),('Drawdown','0%'),('Sharpe Ratio','1'),('End Equity','11000'),('Total Orders','1'),('Total Fees','$1'))):
            text+=f'{i*2} text {k}\n{i*2+1} text {v}\n'
        result=observed_case(text,'candidate','abc')
        self.assertIsNone(result['native']['derived_calmar_from_rounded_native_statistics'])
        self.assertEqual(result['annual_partial'],[])
        self.assertFalse(result['official_export_verified'])
