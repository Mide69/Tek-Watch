"""Unit tests for agent configuration loading."""
import pytest
from unittest.mock import patch


class TestAgentConfig:
    def test_load_config_success(self):
        env = {
            "TEK_WATCH_CUSTOMER_ID": "TT-0042",
            "TEK_WATCH_INGEST_QUEUE_URL": "https://sqs.eu-west-2.amazonaws.com/123/queue",
            "TEK_WATCH_API_KEY": "secret-key",
            "AWS_REGION": "eu-west-2",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict("os.environ", env, clear=False):
            from config import load_config
            config = load_config()
            assert config.customer_id == "TT-0042"
            assert config.ingest_queue_url == "https://sqs.eu-west-2.amazonaws.com/123/queue"
            assert config.api_key == "secret-key"
            assert config.aws_region == "eu-west-2"
            assert config.log_level == "DEBUG"

    def test_load_config_missing_required_exits(self):
        env = {
            "TEK_WATCH_CUSTOMER_ID": "",
            "TEK_WATCH_INGEST_QUEUE_URL": "",
            "TEK_WATCH_API_KEY": "",
        }
        with patch.dict("os.environ", env, clear=False):
            with pytest.raises(SystemExit):
                # Re-import to bypass any module-level caching
                import importlib
                import config as cfg_module
                importlib.reload(cfg_module)
                cfg_module.load_config()

    def test_load_config_defaults(self):
        env = {
            "TEK_WATCH_CUSTOMER_ID": "TT-0001",
            "TEK_WATCH_INGEST_QUEUE_URL": "https://sqs.eu-west-2.amazonaws.com/123/q",
            "TEK_WATCH_API_KEY": "key",
        }
        with patch.dict("os.environ", env, clear=False):
            from config import load_config
            config = load_config()
            assert config.log_level == "INFO"
            assert config.aws_region == "eu-west-2"


class TestRunInterval:
    BASE = {"TEK_WATCH_CUSTOMER_ID": "TT-1", "TEK_WATCH_INGEST_QUEUE_URL": "q", "TEK_WATCH_API_KEY": "k"}

    @pytest.mark.parametrize("raw,expected", [(None, 5), ("15", 15), (" 30 ", 30), ("0", 5), ("soon", 5)])
    def test_interval(self, monkeypatch, raw, expected):
        from config import load_config
        for k, v in self.BASE.items():
            monkeypatch.setenv(k, v)
        if raw is None:
            monkeypatch.delenv("TEK_WATCH_RUN_INTERVAL_MINUTES", raising=False)
        else:
            monkeypatch.setenv("TEK_WATCH_RUN_INTERVAL_MINUTES", raw)
        assert load_config().run_interval_minutes == expected
