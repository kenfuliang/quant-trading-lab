import unittest

from paper_trading.gateway import validate_paper_accounts
from paper_trading.node import build_config


class PaperBoundaryTests(unittest.TestCase):
    def test_accepts_paper_accounts(self):
        self.assertEqual(validate_paper_accounts(["DU1234567"]), ["DU1234567"])

    def test_rejects_live_empty_and_mixed_accounts(self):
        for accounts in ([], ["U1234567"], ["DU1234567", "U1234567"], ["DU"], ["DU123ABC"]):
            with self.subTest(accounts=accounts), self.assertRaises(ValueError):
                validate_paper_accounts(accounts)

    def test_observer_has_no_execution_connection(self):
        config = build_config()
        self.assertEqual(config.exec_clients, {})
        client = next(iter(config.data_clients.values()))
        self.assertEqual((client.ibg_host, client.ibg_port), ("127.0.0.1", 4002))
        self.assertIsNone(client.dockerized_gateway)


if __name__ == "__main__":
    unittest.main()
