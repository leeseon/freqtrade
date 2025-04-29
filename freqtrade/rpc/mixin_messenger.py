"""
This module contains the Mixin Messenger handler implementation
"""
# Standard library imports
import base64
import logging
import uuid
from typing import Any

# Third-party imports
from mixinsdk.clients.client_http import HttpClient_WithAppConfig
from mixinsdk.clients.config import AppConfig

# Local imports
from freqtrade.rpc.rpc import RPC, RPCHandler
from freqtrade.rpc.rpc_types import RPCSendMsg


logger = logging.getLogger(__name__)


class MixinMessenger(RPCHandler):
    """Mixin Messenger handler implementation"""

    def __init__(self, rpc: RPC, config: dict[str, Any]) -> None:
        """
        Init the Mixin Messenger handler
        :param rpc: instance of RPC Helper class
        :param config: Configuration object
        """
        super().__init__(rpc, config)

        self._config = config["mixin_messenger"]
        self._client = None
        self._conversation_ids = self._config.get("conversation_id", [])
        self._notification_settings = self._config.get("notification_settings", {})
        logger.info("Enabling rpc.mixin_messenger ...")
        logger.info(f"Initializing MixinMessenger with config: {self._config}")
        logger.info(f"Notification settings: {self._notification_settings}")
        self._init()

    def _init(self) -> None:
        """Initialize Mixin Messenger client"""
        if self._config.get("enabled", False):
            logger.info("Mixin Messenger is enabled, initializing client...")
            try:
                app_config = AppConfig(
                    client_id=self._config["client_id"],
                    session_id=self._config["session_id"],
                    session_private_key=self._config["private_key"],
                )
                self._client = HttpClient_WithAppConfig(app_config)
                logger.info("Mixin Messenger client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Mixin Messenger client: {e}")
        else:
            logger.warning("Mixin Messenger is disabled in config")

    def cleanup(self) -> None:
        """Cleanup Mixin Messenger client"""
        if self._client:
            self._client = None

    def send_msg(self, msg: RPCSendMsg) -> None:
        """Send message to Mixin Messenger"""
        logger.debug(f"Attempting to send message: {msg}")

        if not self._client:
            logger.error("Cannot send message: Mixin Messenger client is not initialized")
            return

        msg_type = str(msg.get("type", "")).lower()  # Convert to lowercase string
        logger.debug(f"Message type: {msg_type}, Notification settings: {self._notification_settings}")

        # Convert notification settings keys to lowercase for case-insensitive comparison
        notification_settings = {k.lower(): v for k, v in self._notification_settings.items()}

        if msg_type not in notification_settings:
            # logger.warning(f"Message type {msg_type} not found in notification settings")
            return

        if not notification_settings[msg_type]:
            logger.info(f"Message type {msg_type} is disabled in notification settings")
            return

        message = self._format_msg(msg)
        if not message:
            logger.warning("Message formatting returned None")
            return

        for conversation_id in self._conversation_ids:
            try:
                logger.info(f"Sending message to conversation {conversation_id}: {message}")
                self._client.api.message.send_messages({
                    "conversation_id": conversation_id,
                    "message_id": str(uuid.uuid4()),
                    "category": "PLAIN_TEXT",
                    "data": base64.b64encode(message.encode()).decode()
                })
                logger.info(f"Successfully sent message to conversation {conversation_id}")
            except Exception as e:
                logger.error(f"Failed to send message to Mixin Messenger: {e}")

    def _format_msg(self, msg: RPCSendMsg) -> str:
        """Format message for Mixin Messenger"""
        msg_type = str(msg.get("type", "")).lower()  # Convert to lowercase string
        logger.debug(f"Formatting message of type {msg_type}: {msg}")

        if msg_type == "status":
            return f"Status: {msg.get('status', '')}"
        elif msg_type == "warning":
            return f"⚠️ Warning: {msg.get('status', '')}"
        elif msg_type == "startup":
            return f"🚀 Startup: {msg.get('status', '')}"
        elif msg_type == "entry":
            return f"📈 Entry: {msg.get('pair', '')} at {msg.get('open_rate', '')}"
        elif msg_type == "exit":
            return f"📉 Exit: {msg.get('pair', '')} at {msg.get('close_rate', '')}"
        elif msg_type == "strategy_msg":
            return f"📊 Strategy: {msg.get('msg', '')}"

        logger.warning(f"Unknown message type: {msg_type}")
        return None
