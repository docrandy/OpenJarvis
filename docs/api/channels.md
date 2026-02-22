# API Reference: Channels

The `openjarvis.channels` package provides the channel messaging abstraction and the OpenClaw gateway bridge. All public classes and types are documented below.

For usage examples, CLI commands, and configuration, see the [Channels user guide](../user-guide/channels.md). For the architectural design and listener loop internals, see [Channels architecture](../architecture/channels.md).

---

## Types and Enums

### ChannelStatus

Connection status values for a channel. Returned by `BaseChannel.status()`.

::: openjarvis.channels._stubs.ChannelStatus
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### ChannelMessage

Dataclass representing a message received from or sent to a channel. All fields correspond to the JSON payload exchanged with the gateway.

::: openjarvis.channels._stubs.ChannelMessage
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

### ChannelHandler

Type alias for message handler callbacks:

```python
ChannelHandler = Callable[[ChannelMessage], Optional[str]]
```

Handlers are called synchronously from the listener thread when a message arrives. The optional `str` return value is reserved for future auto-reply routing and has no effect in the current implementation.

!!! warning "Thread safety"
    Handlers run on the listener thread, not the caller thread. Protect shared state with locks or `queue.Queue`.

::: openjarvis.channels._stubs.ChannelHandler
    options:
      show_source: true
      show_root_heading: true
      heading_level: 4

---

## BaseChannel

Abstract base class for all channel implementations. Subclasses must implement all six abstract methods and register via `@ChannelRegistry.register("name")`.

```python title="custom_channel.py"
from openjarvis.channels._stubs import BaseChannel, ChannelMessage, ChannelStatus
from openjarvis.core.registry import ChannelRegistry


@ChannelRegistry.register("my-channel")
class MyChannel(BaseChannel):
    channel_id = "my-channel"

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def send(self, channel, content, *, conversation_id="", metadata=None) -> bool: ...
    def status(self) -> ChannelStatus: ...
    def list_channels(self) -> list[str]: ...
    def on_message(self, handler) -> None: ...
```

::: openjarvis.channels._stubs.BaseChannel
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3

---

## OpenClawChannelBridge

`OpenClawChannelBridge` connects to the OpenClaw gateway over WebSocket, with automatic HTTP fallback when the `websockets` package is not installed or a WebSocket send fails. It is registered as `"openclaw"` in `ChannelRegistry`.

```python title="bridge_example.py"
from openjarvis.channels.openclaw_bridge import OpenClawChannelBridge
from openjarvis.channels._stubs import ChannelMessage
from openjarvis.core.events import EventBus

bus = EventBus()
bridge = OpenClawChannelBridge(
    gateway_url="ws://127.0.0.1:18789/ws",
    reconnect_interval=5.0,
    bus=bus,
)


def on_message(msg: ChannelMessage) -> None:
    print(f"[{msg.channel}] {msg.sender}: {msg.content}")


bridge.on_message(on_message)
bridge.connect()

bridge.send("notifications", "Hello!")
channels = bridge.list_channels()

bridge.disconnect()
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gateway_url` | `str` | `ws://127.0.0.1:18789/ws` | WebSocket URL of the OpenClaw gateway |
| `reconnect_interval` | `float` | `5.0` | Seconds to wait before reconnecting after a disconnect |
| `bus` | `EventBus` | `None` | Event bus for publishing `CHANNEL_MESSAGE_RECEIVED` and `CHANNEL_MESSAGE_SENT` events |

### Events Published

| Event | When |
|-------|------|
| `CHANNEL_MESSAGE_RECEIVED` | Message received from gateway WebSocket |
| `CHANNEL_MESSAGE_SENT` | Message successfully delivered via WebSocket or HTTP |

::: openjarvis.channels.openclaw_bridge.OpenClawChannelBridge
    options:
      show_source: true
      show_root_heading: true
      heading_level: 3
