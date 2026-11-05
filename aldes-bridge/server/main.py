"""Punto di avvio principale dell'add-on Aldes Bridge SC150."""
import logging
import signal
import sys
import threading

from .bridge import AldesBridge
from .config import BridgeConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    """Inizializza la configurazione, avvia il listener TLS e il loop MQTT verso Home Assistant."""
    config = BridgeConfig.from_env()
    bridge = AldesBridge(config=config)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    threading.Thread(target=bridge.run_box_listener, daemon=True).start()
    bridge.run_ha_mqtt_loop()


if __name__ == "__main__":
    main()