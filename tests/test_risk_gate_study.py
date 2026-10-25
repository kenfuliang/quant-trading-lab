import unittest
from research.risk_gate_study import reserve

class StudyTests(unittest.TestCase):
    def test_no_duplicate_reservations(self):
        with self.assertRaises(ValueError): reserve(dict(attempts=[{}],status='implementation'),{},None)
        with self.assertRaises(ValueError): reserve(dict(attempts=[],status='completed'),{},None)

if __name__=='__main__': unittest.main()
