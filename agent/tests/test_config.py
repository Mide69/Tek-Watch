"""Unit tests for agent configuration loading."""
import pytest
from unittest.mock import patch


class TestAgentConfig:
    def test_load_config_success(self):
        env = {
            "TRIBE_WATCH_CUSTOMER_ID": "TT-0042",
            "TRIBE_WATCH_INGEST_QUEUE_URL": "https://sqs.eu-west-2.amazonaws.com/123/queue",
            "TRIBE_WATCH_API_KEY": "secret-key",
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
            "TRIBE_WATCH_CUSTOMER_ID": "",
            "TRIBE_WATCH_INGEST_QUEUE_URL": "",
            "TRIBE_WATCH_API_KEY": "",
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
            "TRIBE_WATCH_CUSTOMER_ID": "TT-0001",
            "TRIBE_WATCH_INGEST_QUEUE_URL": "https://sqs.eu-west-2.amazonaws.com/123/q",
            "TRIBE_WATCH_API_KEY": "key",
        }
        with patch.dict("os.environ", env, clear=False):
            from config import load_config
            config = load_config()
            assert config.log_level == "INFO"
            assert config.aws_region == "eu-west-2"
