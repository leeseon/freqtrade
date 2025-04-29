# pragma pylint: disable=missing-docstring, C0103
import logging
from unittest.mock import MagicMock, patch

import pytest

from freqtrade.enums import RPCMessageType
from freqtrade.rpc.mixin_messenger import MixinMessenger
from tests.conftest import get_patched_freqtradebot, log_has

# 32 bytes Ed25519 private key for testing
TEST_PRIVATE_KEY = "1234567890123456789012345678901234567890123456789012345678901234"

def test__init__(mocker, default_conf, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    default_conf["mixin_messenger"] = {
        "enabled": True,
        "api_url": "https://api.mixin.one",
        "client_id": "test_client_id",
        "session_id": "test_session_id",
        "private_key": TEST_PRIVATE_KEY,
        "conversation_id": ["test_conversation_id"],
        "notification_settings": {
            "status": True,
            "warning": True,
            "startup": True,
            "entry": True,
            "exit": True,
            "strategy_msg": True,
        },
    }

    with patch("mixinsdk.clients.client_http.HttpClient_WithAppConfig") as client_mock:
        client_mock.return_value = MagicMock()
        rpc = MixinMessenger(get_patched_freqtradebot(mocker, default_conf).rpc, default_conf)
        assert rpc._client is not None
        assert log_has("Enabling rpc.mixin_messenger ...", caplog)


def test_send_msg(mocker, default_conf) -> None:
    default_conf["mixin_messenger"] = {
        "enabled": True,
        "api_url": "https://api.mixin.one",
        "client_id": "test_client_id",
        "session_id": "test_session_id",
        "private_key": TEST_PRIVATE_KEY,
        "conversation_id": ["test_conversation_id"],
        "notification_settings": {
            "status": True,
            "warning": True,
            "startup": True,
            "entry": True,
            "exit": True,
            "strategy_msg": True,
        },
    }

    with patch("mixinsdk.clients.client_http.HttpClient_WithAppConfig") as client_mock, \
         patch("mixinsdk.clients._requests.HttpRequest.post") as post_mock:
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        post_mock.return_value = mock_response

        # Mock Mixin client
        mock_client = MagicMock()
        mock_api = MagicMock()
        mock_message = MagicMock()
        mock_api.message = mock_message
        mock_client.api = mock_api
        client_mock.return_value = mock_client

        rpc = MixinMessenger(get_patched_freqtradebot(mocker, default_conf).rpc, default_conf)

        # Test status message
        msg = {"type": RPCMessageType.STATUS, "status": "test status"}
        rpc.send_msg(msg)
        assert post_mock.call_count == 1

        # Test warning message
        msg = {"type": RPCMessageType.WARNING, "status": "test warning"}
        rpc.send_msg(msg)
        assert post_mock.call_count == 2

        # Test startup message
        msg = {"type": RPCMessageType.STARTUP, "status": "test startup"}
        rpc.send_msg(msg)
        assert post_mock.call_count == 3

        # Test entry message
        msg = {"type": RPCMessageType.ENTRY, "pair": "BTC/USDT", "open_rate": 50000}
        rpc.send_msg(msg)
        assert post_mock.call_count == 4

        # Test exit message
        msg = {"type": RPCMessageType.EXIT, "pair": "BTC/USDT", "close_rate": 55000}
        rpc.send_msg(msg)
        assert post_mock.call_count == 5

        # Test strategy message
        msg = {"type": RPCMessageType.STRATEGY_MSG, "msg": "test strategy"}
        rpc.send_msg(msg)
        assert post_mock.call_count == 6


def test_cleanup(mocker, default_conf) -> None:
    default_conf["mixin_messenger"] = {
        "enabled": True,
        "api_url": "https://api.mixin.one",
        "client_id": "test_client_id",
        "session_id": "test_session_id",
        "private_key": TEST_PRIVATE_KEY,
        "conversation_id": ["test_conversation_id"],
        "notification_settings": {
            "status": True,
            "warning": True,
            "startup": True,
            "entry": True,
            "exit": True,
            "strategy_msg": True,
        },
    }

    with patch("mixinsdk.clients.client_http.HttpClient_WithAppConfig") as client_mock:
        client_mock.return_value = MagicMock()
        rpc = MixinMessenger(get_patched_freqtradebot(mocker, default_conf).rpc, default_conf)
        assert rpc._client is not None
        rpc.cleanup()
        assert rpc._client is None 