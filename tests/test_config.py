import tempfile
import unittest
from pathlib import Path


class ConfigTest(unittest.TestCase):
    def test_loads_brokers_and_default_from_env_file(self):
        from services.config import load_app_config

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "PORTFOLIO_BROKERS=IBKR, Schwab, Firstrade, Robinhood, Manual\n"
                "DEFAULT_BROKER=Robinhood\n",
                encoding="utf-8",
            )

            config = load_app_config(env_path)

        self.assertEqual(config.brokers, ["IBKR", "Schwab", "Firstrade", "Robinhood", "Manual"])
        self.assertEqual(config.default_broker, "Robinhood")

    def test_falls_back_when_env_default_is_not_in_brokers(self):
        from services.config import load_app_config

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "PORTFOLIO_BROKERS=IBKR,Schwab\n"
                "DEFAULT_BROKER=Unknown\n",
                encoding="utf-8",
            )

            config = load_app_config(env_path)

        self.assertEqual(config.brokers, ["IBKR", "Schwab"])
        self.assertEqual(config.default_broker, "IBKR")

    def test_broker_index_prefers_last_used_then_default(self):
        from services.config import broker_index

        brokers = ["IBKR", "Schwab", "Firstrade", "Manual"]

        self.assertEqual(broker_index(brokers, default_broker="IBKR", last_broker="Firstrade"), 2)
        self.assertEqual(broker_index(brokers, default_broker="Schwab", last_broker="Unknown"), 1)
        self.assertEqual(broker_index(brokers, default_broker="Unknown", last_broker=None), 0)


if __name__ == "__main__":
    unittest.main()
