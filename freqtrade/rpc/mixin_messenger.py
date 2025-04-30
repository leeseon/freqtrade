"""
This module contains the Mixin Messenger handler implementation
"""
# Standard library imports
import base64
import logging
import uuid
import time
import hashlib
import jwt
import requests
import json
from typing import Any
from cryptography.hazmat.primitives.asymmetric import ed25519

# Local imports
from freqtrade.rpc.rpc import RPC, RPCHandler
from freqtrade.rpc.rpc_types import RPCSendMsg, RPCMessageType

logger = logging.getLogger(__name__)

def sign_authentication_token(
    user_id,
    session_id,
    private_key: str,
    method,
    uri,
    bodystring: str = None,
    iat: int = None,
    exp: int = None,
    jti: str = None,
):
    """
    JWT Structure: https://developers.mixin.one/docs/api/guide
    """
    alg = "EdDSA"
    
    # Convert hex string to bytes and create Ed25519 private key
    if isinstance(private_key, str):
        private_key = bytes.fromhex(private_key.replace('0x', ''))
        try:
            key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        except Exception as e:
            logger.error(f"Failed to create Ed25519 private key: {e}")
            raise ValueError("Invalid private key format") from e

    jwt_headers = {
        "alg": alg,
        "typ": "JWT",
    }

    bodystring = bodystring if bodystring else ""
    hashresult = hashlib.sha256((method + uri + bodystring).encode("utf-8")).hexdigest()
    iat = int(time.time()) if iat is None else iat
    exp = iat + 600 if exp is None else exp
    jti = str(uuid.uuid4()) if jti is None else jti
    payload = {
        "uid": user_id,
        "sid": session_id,
        "iat": iat,
        "exp": exp,
        "jti": jti,
        "sig": hashresult,
        "scp": "FULL",
    }

    return jwt.encode(payload, key, algorithm=alg, headers=jwt_headers)

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
        self._conversation_ids = self._config.get("conversation_id", [])
        self._notification_settings = self._config.get("notification_settings", {})
        self._api_url = self._config.get("api_url", "https://api.mixin.one")
        logger.info("Enabling rpc.mixin_messenger ...")
        logger.info(f"Initializing MixinMessenger with config: {self._config}")
        logger.info(f"Notification settings: {self._notification_settings}")

    def _get_auth_token(self, method: str, uri: str, body: str = "") -> str:
        """
        Generate authentication token for Mixin API
        """
        try:
            return sign_authentication_token(
                self._config["client_id"],
                self._config["session_id"],
                self._config["private_key"],
                method,
                uri,
                body
            )
        except Exception as e:
            logger.error(f"Failed to generate auth token: {e}")
            raise

    def _make_request(self, method: str, path: str, data: dict = None) -> dict:
        """
        Make request to Mixin API
        
        Args:
            method: HTTP method
            path: API path
            data: Request data
            
        Returns:
            Response data
        """
        # Prepare request
        url = f"{self._api_url}{path}"
        body = json.dumps(data) if data else ""
        
        # Generate authentication token
        token = self._get_auth_token(method, path, body)
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-Request-ID": str(int(time.time() * 1000))
        }
        
        # Make request
        try:
            logger.debug(f"MixinMessenger: 发送请求到 {url}")
            logger.debug(f"MixinMessenger: 请求头: {headers}")
            logger.debug(f"MixinMessenger: 请求体: {body}")
            
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=body)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            # Check response
            response.raise_for_status()
            response_data = response.json()
            logger.debug(f"MixinMessenger: 响应数据: {response_data}")
            return response_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"MixinMessenger: 请求错误: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"MixinMessenger: 响应状态码: {e.response.status_code}")
                logger.error(f"MixinMessenger: 响应内容: {e.response.text}")
            raise

    def send_msg(self, msg: dict) -> None:
        """
        Send message to Mixin Messenger.
        """
        logger.debug(f"MixinMessenger: 收到消息: {msg}")
        msg_type = msg.get("type")
        if not msg_type:
            logger.debug("MixinMessenger: 消息类型为空")
            return

        if not self._config.get("notification_settings", {}).get(msg_type, False):
            logger.debug(f"MixinMessenger: 消息类型 {msg_type} 未启用")
            return

        try:
            if msg_type == RPCMessageType.STRATEGY_MSG:
                logger.debug(f"MixinMessenger: 处理策略消息: {msg.get('msg')}")
                self._send_strategy_msg(msg.get("msg", ""))
            elif msg_type == RPCMessageType.STATUS:
                logger.debug(f"MixinMessenger: 处理状态消息: {msg.get('status')}")
                self._send_status_msg(msg.get("status", ""))
            elif msg_type == RPCMessageType.WARNING:
                logger.debug(f"MixinMessenger: 处理警告消息: {msg.get('status')}")
                self._send_warning_msg(msg.get("status", ""))
            elif msg_type == RPCMessageType.STARTUP:
                logger.debug(f"MixinMessenger: 处理启动消息: {msg.get('status')}")
                self._send_startup_msg(msg.get("status", ""))
            elif msg_type == RPCMessageType.ENTRY:
                logger.debug(f"MixinMessenger: 处理开仓消息: {msg.get('pair')}")
                self._send_entry_msg(msg)
            elif msg_type == RPCMessageType.EXIT:
                logger.debug(f"MixinMessenger: 处理平仓消息: {msg.get('pair')}")
                self._send_exit_msg(msg)
            else:
                logger.debug(f"MixinMessenger: 未知消息类型: {msg_type}")
        except Exception as e:
            logger.exception(f"MixinMessenger: 发送消息时发生异常: {str(e)}")

    def _send_message(self, conversation_id: str, message: str) -> bool:
        """
        Send message to Mixin conversation
        """
        try:
            # Prepare message data
            data = {
                "conversation_id": conversation_id,
                "message_id": str(uuid.uuid4()),
                "category": "PLAIN_TEXT",
                "data": base64.b64encode(message.encode()).decode()
            }
            
            # Send message
            response = self._make_request("POST", "/messages", data)
            
            # Check response
            if response.get("data", {}).get("message_id"):
                logger.debug(f"MixinMessenger: 消息已发送到会话 {conversation_id}")
                return True
            else:
                logger.error(f"MixinMessenger: 发送消息到会话 {conversation_id} 失败")
                logger.error(f"MixinMessenger: 响应数据: {response}")
                return False
                
        except Exception as e:
            logger.exception(f"MixinMessenger: 发送消息到会话 {conversation_id} 时发生异常: {e}")
            return False

    def _send_strategy_msg(self, msg: str) -> None:
        """发送策略消息"""
        for conversation_id in self._conversation_ids:
            self._send_message(conversation_id, msg)

    def _send_status_msg(self, msg: str) -> None:
        """发送状态消息"""
        for conversation_id in self._conversation_ids:
            self._send_message(conversation_id, f"状态: {msg}")

    def _send_warning_msg(self, msg: str) -> None:
        """发送警告消息"""
        for conversation_id in self._conversation_ids:
            self._send_message(conversation_id, f"⚠️ 警告: {msg}")

    def _send_startup_msg(self, msg: str) -> None:
        """发送启动消息"""
        for conversation_id in self._conversation_ids:
            self._send_message(conversation_id, f"🚀 启动: {msg}")

    def _send_entry_msg(self, msg: dict) -> None:
        """发送开仓消息"""
        pair = msg.get("pair", "")
        open_rate = msg.get("open_rate", "")
        current_rate = msg.get("current_rate", "")
        amount = msg.get("amount", "")
        stake_amount = msg.get("stake_amount", "")
        order_type = msg.get("order_type", "")
        enter_tag = msg.get("enter_tag", "")

        message = (
            f"📈 开仓\n"
            f"交易对: {pair}\n"
            f"开仓价格: {open_rate}\n"
            f"当前价格: {current_rate}\n"
            f"数量: {amount}\n"
            f"投入金额: {stake_amount}\n"
            f"订单类型: {order_type}\n"
            f"标签: {enter_tag}"
        )

        for conversation_id in self._conversation_ids:
            self._send_message(conversation_id, message)

    def _send_exit_msg(self, msg: dict) -> None:
        """发送平仓消息"""
        pair = msg.get("pair", "")
        gain = msg.get("gain", "")
        profit = msg.get("profit", "")
        open_rate = msg.get("open_rate", "")
        close_rate = msg.get("close_rate", "")
        amount = msg.get("amount", "")
        order_type = msg.get("order_type", "")
        exit_reason = msg.get("exit_reason", "")

        message = (
            f"📉 平仓\n"
            f"交易对: {pair}\n"
            f"收益率: {gain}\n"
            f"利润: {profit}\n"
            f"开仓价格: {open_rate}\n"
            f"平仓价格: {close_rate}\n"
            f"数量: {amount}\n"
            f"订单类型: {order_type}\n"
            f"平仓原因: {exit_reason}"
        )

        for conversation_id in self._conversation_ids:
            self._send_message(conversation_id, message)
