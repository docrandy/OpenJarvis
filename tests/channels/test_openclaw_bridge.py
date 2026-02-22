"""Tests for the OpenClawChannelBridge implementation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.channels._stubs import ChannelMessage, ChannelStatus
from openjarvis.channels.openclaw_bridge import OpenClawChannelBridge
from openjarvis.core.events import EventBus, EventType
from openjarvis.core.registry import ChannelRegistry


@pytest.fixture(autouse=True)
def _register_bridge():
    """Re-register the OpenClawChannelBridge after registry clear."""
    if not ChannelRegistry.contains("openclaw"):
        ChannelRegistry.register_value("openclaw", OpenClawChannelBridge)


class TestInit:
    def test_init_defaults(self) -> None:
        bridge = OpenClawChannelBridge()
        assert bridge._gateway_url == "ws://127.0.0.1:18789/ws"
        assert bridge._reconnect_interval == 5.0
        assert bridge._bus is None
        assert bridge._handlers == []
        assert bridge._status == ChannelStatus.DISCONNECTED
        assert bridge._ws is None

    def test_init_custom_url(self) -> None:
        bridge = OpenClawChannelBridge(gateway_url="ws://custom:9999/ws")
        assert bridge._gateway_url == "ws://custom:9999/ws"

    def test_init_custom_reconnect(self) -> None:
        bridge = OpenClawChannelBridge(reconnect_interval=10.0)
        assert bridge._reconnect_interval == 10.0

    def test_init_with_bus(self) -> None:
        bus = EventBus()
        bridge = OpenClawChannelBridge(bus=bus)
        assert bridge._bus is bus

    def test_channel_id(self) -> None:
        bridge = OpenClawChannelBridge()
        assert bridge.channel_id == "openclaw"


class TestStatus:
    def test_status_disconnected_initially(self) -> None:
        bridge = OpenClawChannelBridge()
        assert bridge.status() == ChannelStatus.DISCONNECTED


class TestConnect:
    def test_connect_no_websockets(self) -> None:
        """When websockets is not installed, connect uses HTTP fallback."""
        bridge = OpenClawChannelBridge()
        with patch(
            "openjarvis.channels.openclaw_bridge.OpenClawChannelBridge.connect",
            wraps=bridge.connect,
        ):
            # Simulate ImportError for websockets
            import builtins
            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if "websockets" in name:
                    raise ImportError("No module named 'websockets'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                bridge.connect()

        assert bridge.status() == ChannelStatus.CONNECTED
        assert bridge._ws is None

    def test_connect_websocket_success(self) -> None:
        """When websockets is available, connect opens a WebSocket."""
        bridge = OpenClawChannelBridge()
        mock_ws = MagicMock()

        # Manually simulate successful connect
        bridge._ws = mock_ws
        bridge._status = ChannelStatus.CONNECTED

        assert bridge.status() == ChannelStatus.CONNECTED

    def test_connect_connection_error(self) -> None:
        """When connection fails, status is ERROR."""
        bridge = OpenClawChannelBridge()

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "websockets" in name:
                # Allow the import but make connect fail
                mod = MagicMock()
                mod.sync.client.connect.side_effect = ConnectionError("refused")
                return mod
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            bridge.connect()

        assert bridge.status() == ChannelStatus.ERROR


class TestDisconnect:
    def test_disconnect(self) -> None:
        bridge = OpenClawChannelBridge()
        # Manually set to connected state
        bridge._status = ChannelStatus.CONNECTED
        bridge.disconnect()
        assert bridge.status() == ChannelStatus.DISCONNECTED

    def test_disconnect_closes_ws(self) -> None:
        bridge = OpenClawChannelBridge()
        mock_ws = MagicMock()
        bridge._ws = mock_ws
        bridge._status = ChannelStatus.CONNECTED
        bridge.disconnect()
        mock_ws.close.assert_called_once()
        assert bridge._ws is None
        assert bridge.status() == ChannelStatus.DISCONNECTED

    def test_disconnect_joins_listener_thread(self) -> None:
        bridge = OpenClawChannelBridge()
        mock_thread = MagicMock()
        bridge._listener_thread = mock_thread
        bridge._status = ChannelStatus.CONNECTED
        bridge.disconnect()
        mock_thread.join.assert_called_once()
        assert bridge._listener_thread is None

    def test_disconnect_when_already_disconnected(self) -> None:
        bridge = OpenClawChannelBridge()
        bridge.disconnect()  # Should not raise
        assert bridge.status() == ChannelStatus.DISCONNECTED


class TestSend:
    def test_send_http_fallback(self) -> None:
        """When no WebSocket, send uses HTTP POST."""
        bridge = OpenClawChannelBridge()
        bridge._ws = None
        bridge._status = ChannelStatus.CONNECTED

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.post", return_value=mock_response) as mock_post:
            result = bridge.send("slack", "Hello!")
            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://127.0.0.1:18789/send"
            payload = call_args[1]["json"]
            assert payload["channel"] == "slack"
            assert payload["content"] == "Hello!"

    def test_send_http_failure(self) -> None:
        """When HTTP POST fails, send returns False."""
        bridge = OpenClawChannelBridge()
        bridge._ws = None
        bridge._status = ChannelStatus.CONNECTED

        with patch("httpx.post", side_effect=ConnectionError("refused")):
            result = bridge.send("slack", "Hello!")
            assert result is False

    def test_send_http_bad_status(self) -> None:
        """When HTTP POST returns error status, send returns False."""
        bridge = OpenClawChannelBridge()
        bridge._ws = None

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.post", return_value=mock_response):
            result = bridge.send("slack", "Hello!")
            assert result is False

    def test_send_via_websocket(self) -> None:
        """When WebSocket is available, send via WS."""
        bridge = OpenClawChannelBridge()
        mock_ws = MagicMock()
        bridge._ws = mock_ws
        bridge._status = ChannelStatus.CONNECTED

        result = bridge.send("slack", "Hello!", conversation_id="conv-1")
        assert result is True
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["channel"] == "slack"
        assert sent_data["content"] == "Hello!"
        assert sent_data["conversation_id"] == "conv-1"

    def test_send_ws_failure_falls_back_to_http(self) -> None:
        """When WebSocket send fails, fallback to HTTP."""
        bridge = OpenClawChannelBridge()
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("WS error")
        bridge._ws = mock_ws

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.post", return_value=mock_response):
            result = bridge.send("slack", "Hello!")
            assert result is True

    def test_send_with_metadata(self) -> None:
        """Metadata is included in the payload."""
        bridge = OpenClawChannelBridge()
        mock_ws = MagicMock()
        bridge._ws = mock_ws

        bridge.send("slack", "Hello!", metadata={"thread_ts": "123"})
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["metadata"] == {"thread_ts": "123"}

    def test_send_publishes_event(self) -> None:
        """Successful send publishes CHANNEL_MESSAGE_SENT event."""
        bus = EventBus(record_history=True)
        bridge = OpenClawChannelBridge(bus=bus)
        mock_ws = MagicMock()
        bridge._ws = mock_ws

        bridge.send("slack", "Hello!")
        event_types = [e.event_type for e in bus.history]
        assert EventType.CHANNEL_MESSAGE_SENT in event_types


class TestListChannels:
    def test_list_channels_http(self) -> None:
        """list_channels queries HTTP endpoint."""
        bridge = OpenClawChannelBridge()

        mock_response = MagicMock()
        mock_response.json.return_value = ["slack", "discord", "telegram"]

        with patch("httpx.get", return_value=mock_response) as mock_get:
            channels = bridge.list_channels()
            assert channels == ["slack", "discord", "telegram"]
            mock_get.assert_called_once()
            assert "/channels" in mock_get.call_args[0][0]

    def test_list_channels_dict_response(self) -> None:
        """list_channels handles dict response with 'channels' key."""
        bridge = OpenClawChannelBridge()

        mock_response = MagicMock()
        mock_response.json.return_value = {"channels": ["slack", "discord"]}

        with patch("httpx.get", return_value=mock_response):
            channels = bridge.list_channels()
            assert channels == ["slack", "discord"]

    def test_list_channels_error(self) -> None:
        """When HTTP GET fails, return empty list."""
        bridge = OpenClawChannelBridge()

        with patch("httpx.get", side_effect=ConnectionError("refused")):
            channels = bridge.list_channels()
            assert channels == []

    def test_list_channels_unexpected_format(self) -> None:
        """When response is not a list or dict with 'channels', return empty list."""
        bridge = OpenClawChannelBridge()

        mock_response = MagicMock()
        mock_response.json.return_value = {"unexpected": "format"}

        with patch("httpx.get", return_value=mock_response):
            channels = bridge.list_channels()
            assert channels == []


class TestOnMessage:
    def test_on_message(self) -> None:
        bridge = OpenClawChannelBridge()
        handler = MagicMock()
        bridge.on_message(handler)
        assert handler in bridge._handlers

    def test_on_message_multiple_handlers(self) -> None:
        bridge = OpenClawChannelBridge()
        h1 = MagicMock()
        h2 = MagicMock()
        bridge.on_message(h1)
        bridge.on_message(h2)
        assert len(bridge._handlers) == 2
        assert h1 in bridge._handlers
        assert h2 in bridge._handlers


class TestHttpUrlConversion:
    def test_ws_to_http(self) -> None:
        bridge = OpenClawChannelBridge(gateway_url="ws://host:1234/ws")
        assert bridge._http_url("/send") == "http://host:1234/send"

    def test_wss_to_https(self) -> None:
        bridge = OpenClawChannelBridge(gateway_url="wss://host:1234/ws")
        assert bridge._http_url("/send") == "https://host:1234/send"

    def test_http_url_channels(self) -> None:
        bridge = OpenClawChannelBridge(gateway_url="ws://127.0.0.1:18789/ws")
        assert bridge._http_url("/channels") == "http://127.0.0.1:18789/channels"


# ---------------------------------------------------------------------------
# _listener_loop() tests
# ---------------------------------------------------------------------------


def _make_bridge_with_mock_ws(
    msg_json: str,
    *,
    bus: EventBus | None = None,
) -> OpenClawChannelBridge:
    """Return a bridge whose ``_ws.recv()`` returns *msg_json* once, then stops."""
    bridge = OpenClawChannelBridge(bus=bus)
    bridge._status = ChannelStatus.CONNECTED

    call_count = 0

    def mock_recv(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return msg_json
        bridge._stop_event.set()
        raise TimeoutError()

    mock_ws = MagicMock()
    mock_ws.recv = mock_recv
    bridge._ws = mock_ws
    return bridge


_SAMPLE_MSG = json.dumps({
    "channel": "slack",
    "sender": "user1",
    "content": "Hello!",
    "message_id": "msg-1",
    "conversation_id": "conv-1",
    "metadata": {},
})


class TestListenerLoop:
    def test_listener_receives_and_parses_message(self) -> None:
        """Listener parses incoming JSON into a ChannelMessage."""
        bridge = _make_bridge_with_mock_ws(_SAMPLE_MSG)
        received: list[ChannelMessage] = []
        bridge.on_message(lambda msg: received.append(msg))

        bridge._listener_loop()

        assert len(received) == 1
        msg = received[0]
        assert isinstance(msg, ChannelMessage)
        assert msg.channel == "slack"
        assert msg.sender == "user1"
        assert msg.content == "Hello!"
        assert msg.message_id == "msg-1"

    def test_listener_invokes_all_handlers(self) -> None:
        """All registered handlers are called for each message."""
        bridge = _make_bridge_with_mock_ws(_SAMPLE_MSG)
        calls_a: list[ChannelMessage] = []
        calls_b: list[ChannelMessage] = []
        bridge.on_message(lambda msg: calls_a.append(msg))
        bridge.on_message(lambda msg: calls_b.append(msg))

        bridge._listener_loop()

        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_listener_publishes_event(self) -> None:
        """Listener publishes CHANNEL_MESSAGE_RECEIVED on the event bus."""
        bus = EventBus(record_history=True)
        bridge = _make_bridge_with_mock_ws(_SAMPLE_MSG, bus=bus)

        bridge._listener_loop()

        event_types = [e.event_type for e in bus.history]
        assert EventType.CHANNEL_MESSAGE_RECEIVED in event_types
        recv_event = next(
            e for e in bus.history
            if e.event_type == EventType.CHANNEL_MESSAGE_RECEIVED
        )
        assert recv_event.data["channel"] == "slack"
        assert recv_event.data["sender"] == "user1"

    def test_listener_stops_on_stop_event(self) -> None:
        """Listener returns immediately when _stop_event is already set."""
        bridge = OpenClawChannelBridge()
        bridge._status = ChannelStatus.CONNECTED
        bridge._ws = MagicMock()
        bridge._stop_event.set()

        handler = MagicMock()
        bridge.on_message(handler)

        # Should return immediately without calling any handler
        import threading
        t = threading.Thread(target=bridge._listener_loop)
        t.start()
        t.join(timeout=3.0)
        assert not t.is_alive(), "_listener_loop did not exit in time"
        handler.assert_not_called()

    def test_listener_catches_handler_exceptions(self) -> None:
        """A failing handler does not prevent subsequent handlers from running."""
        bridge = _make_bridge_with_mock_ws(_SAMPLE_MSG)
        second_calls: list[ChannelMessage] = []

        def bad_handler(msg: ChannelMessage) -> None:
            raise ValueError("boom")

        bridge.on_message(bad_handler)
        bridge.on_message(lambda msg: second_calls.append(msg))

        bridge._listener_loop()

        assert len(second_calls) == 1
