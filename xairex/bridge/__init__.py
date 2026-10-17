"""Browser bridge (G23, D42/D43): loopback WebSocket link to the Xairex extension.

The extension lives in ``extension/`` at the project root; it is loaded
manually in Chrome/Edge ("Load unpacked") and connects to
``ws://127.0.0.1:<bridge.port>`` whenever Xairex runs. All traffic stays on
loopback; nothing is ever downloaded or uploaded.
"""

from xairex.bridge.server import BridgeServer
from xairex.bridge.store import ActivityStore

__all__ = ["ActivityStore", "BridgeServer"]
