"""Server principale Aldes InspirAIR Home SC150 Bridge."""
import json
import logging
import os
import signal
import socket
import struct
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone

from . import __version__, mqtt
from .tls import server_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
_log = logging.getLogger("aldes-sc150")

TELEMETRY_CACHE = "/config/aldes/telemetry.json"

VMC_CODE_TO_PRESET = {
    "V": "Quotidiano (V)",
    "X": "Modalita X",
    "Y": "Modalita Y",
    "W": "Vacanze (W)",
    "Z": "Programmazione (Z)",
}
VMC_PRESET_TO_CODE = {v.lower(): k for k, v in VMC_CODE_TO_PRESET.items()}

# (suffisso_id, chiave_json, nome, unita, device_class, state_class, icona, enabled_by_default, is_float)
SENSORS = [
    ("outside_tpt", "outside_tpt", "Temperatura Aria Esterna", "°C", "temperature", "measurement", "mdi:thermometer", True, True),
    ("ext_tpt", "ext_tpt", "Temperatura Aria Estratta", "°C", "temperature", "measurement", "mdi:home-thermometer", True, True),
    ("reject_tpt", "reject_tpt", "Temperatura Aria Reimmessa", "°C", "temperature", "measurement", "mdi:thermometer-chevron-down", True, True),
    ("extf_flw", "extf_flw", "Portata Estrazione", "m³/h", None, "measurement", "mdi:weather-windy", True, False),
    ("ffe_flw", "ffe_flw", "Portata Immissione", "m³/h", None, "measurement", "mdi:air-filter", True, False),
    ("extf_spd", "extf_spd", "Velocita Ventola Estrazione", "rpm", None, "measurement", "mdi:fan", True, False),
    ("vi_spd", "vi_spd", "Velocita Ventola Immissione", "rpm", None, "measurement", "mdi:fan", True, False),
    ("set_spd", "set_spd", "Livello Velocita VMC", None, None, "measurement", "mdi:speedometer", True, False),
    ("current_mode", "current_mode", "Codice Modalita Attiva", None, None, None, "mdi:tune", True, None),
    ("ff_cpt", "ff_cpt", "Contatore Usura Filtro", "d", None, "measurement", "mdi:air-filter", True, False),
    ("dep_ind", "dep_ind", "Indice Depressione Filtri", None, None, "measurement", "mdi:gauge", True, False),
    ("dtb_ind", "dtb_ind", "Stato Bypass", None, None, "measurement", "mdi:valve", True, False),
    ("vers_uc", "Vers_UC", "Versione Firmware UC", None, None, None, "mdi:chip", True, False),
    ("vers_w", "Vers_W", "Versione Firmware Wi-Fi", None, None, None, "mdi:wifi-cog", True, None),
    # Sensori a valore zero: creati ma disabilitati di default
    ("rssi", "RSSI", "Segnale Wi-Fi Box", None, None, None, "mdi:wifi", False, None),
    ("co2_vmc", "Co2_vmc", "CO2 VMC", "ppm", "carbon_dioxide", "measurement", "mdi:molecule-co2", False, True),
    ("pm25_vmc", "Pm25_Vmc", "PM2.5 VMC", "Âµg/mÂ³", "pm25", "measurement", "mdi:blur", False, True),
    ("voc_vmc", "Voc_Vmc", "VOC VMC", "ppm", None, "measurement", "mdi:chemical-weapon", False, False),
    ("cve_csn", "cve_csn", "Consumo Ventola Estrazione", "W", "power", "measurement", "mdi:flash", False, False),
    ("vi_csn", "vi_csn", "Consumo Ventola Immissione", "W", "power", "measurement", "mdi:flash", False, False),
    ("tte_csn", "tte_csn", "Consumo Totale VMC", "W", "power", "measurement", "mdi:flash", False, False),
    ("echange_pwr", "echange_pwr", "Potenza Scambiatore", "W", "power", "measurement", "mdi:heat-wave", False, False),
]


def parse_json_payload(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str):
        return None
    pos = raw.find("{")
    if pos < 0:
        return None
    try:
        data = json.loads(raw[pos:])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def detect_mqtt_broker():
    host = (os.environ.get("HA_MQTT_HOST") or "").strip()
    port = int(os.environ.get("HA_MQTT_PORT") or 1883)
    user = (os.environ.get("HA_MQTT_USER") or "").strip() or None
    pw = (os.environ.get("HA_MQTT_PASSWORD") or "").strip() or None
    if host:
        return host, port, user, pw

    token = os.environ.get("SUPERVISOR_TOKEN")
    if token:
        try:
            req = urllib.request.Request(
                "http://supervisor/services/mqtt",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                d = json.loads(resp.read()).get("data", {})
                if d.get("host"):
                    _log.info("Broker MQTT rilevato via Supervisor API: %s:%s", d["host"], d.get("port", 1883))
                    return (
                        d["host"],
                        int(d.get("port", 1883)),
                        user or d.get("username"),
                        pw or d.get("password"),
                    )
        except Exception as exc:
            _log.warning("Auto-detect Supervisor MQTT non riuscito: %s", exc)

    return "core-mosquitto", port, user, pw


class SC150Bridge:
    def __init__(self, listen_port=18883, prefix="aldes"):
        self.listen_port = listen_port
        self.prefix = prefix
        self.box_sock = None
        self.box_lock = threading.Lock()
        self.box_connected = False
        self.product_id = "98D8636921CA_AIR"
        self.cmd_id = 1
        self.pkt_id = 1
        self.ha_sock = None
        self.ha_lock = threading.Lock()
        self.ha_pkt_id = 1
        self.last_data = self._load_cache()

    def _load_cache(self):
        try:
            with open(TELEMETRY_CACHE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    if d.get("productid"):
                        self.product_id = d["productid"]
                    _log.info("Telemetria precedente caricata da cache (%d campi)", len(d))
                    return d
        except Exception:
            pass
        return {}

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(TELEMETRY_CACHE), exist_ok=True)
            tmp = TELEMETRY_CACHE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.last_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, TELEMETRY_CACHE)
        except Exception:
            pass

    def send_to_box(self, method, params):
        with self.box_lock:
            self.cmd_id += 1
            body = json.dumps(
                {"id": self.cmd_id, "jsonrpc": "2.0", "method": method, "params": params},
                ensure_ascii=False,
            )
            topic = f"devices/{self.product_id}/messages/devicebound"
            if not self.box_sock:
                _log.warning("Comando NON inviato (Connect Box non connessa): %s", body)
                return
            self.pkt_id = (self.pkt_id % 65530) + 1
            pkt = mqtt.build_publish(topic, body, qos=1, pkt_id=self.pkt_id)
            try:
                self.box_sock.sendall(pkt)
                _log.info("--> COMANDO INVIATO ALLA BOX [%s]: %s", topic, body)
            except Exception as exc:
                _log.error("Errore invio comando alla box: %s", exc)

    def run_box_listener(self):
        ctx = server_context("aldesiotsuite.azure-devices.net")
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.listen_port))
        srv.listen(4)
        _log.info("=== Aldes Bridge SC150 v%s in ascolto TLS su 0.0.0.0:%d ===", __version__, self.listen_port)
        while True:
            try:
                client, addr = srv.accept()
                tls_sock = ctx.wrap_socket(client, server_side=True)
                _log.info("Connect Box collegata da %s:%d", addr[0], addr[1])
                threading.Thread(target=self._handle_box_session, args=(tls_sock,), daemon=True).start()
            except Exception as exc:
                _log.warning("Handshake TLS fallito: %s", exc)

    def _handle_box_session(self, sock):
        with self.box_lock:
            old = self.box_sock
            self.box_sock = sock
            self.box_connected = True
        if old:
            try:
                old.close()
            except Exception:
                pass
        self._ha_pub(f"{self.prefix}/health/box_connected", "true")
        reader = mqtt.MQTTReader(sock)
        try:
            while True:
                pkt = reader.read_packet()
                if pkt is None:
                    break
                ptype, flags, body, _ = pkt
                if ptype == mqtt.PT_CONNECT:
                    info = mqtt.parse_connect(body)
                    if info.get("client_id"):
                        self.product_id = info["client_id"]
                    sock.settimeout(max(90, info.get("keepalive", 60) * 2))
                    sock.sendall(mqtt.build_connack(0))
                    _log.info("MQTT CONNECT da Box: client_id=%s", self.product_id)
                elif ptype == mqtt.PT_SUBSCRIBE:
                    pid, topics = mqtt.parse_subscribe(body)
                    for t, _ in topics:
                        if "devices/" in t:
                            parts = t.split("/")
                            if len(parts) > 1 and parts[1]:
                                self.product_id = parts[1]
                    sock.sendall(mqtt.build_suback(pid, [min(q, 2) for _, q in topics]))
                    _log.info("Box sottoscritta a: %s", [t for t, _ in topics])
                elif ptype == mqtt.PT_PINGREQ:
                    sock.sendall(mqtt.build_pingresp())
                elif ptype == mqtt.PT_PUBLISH:
                    topic, qos, pid, payload = mqtt.parse_publish_full(body, flags)
                    if qos == 1:
                        sock.sendall(mqtt.build_puback(pid))
                    elif qos == 2:
                        sock.sendall(mqtt.build_pubrec(pid))
                    data = parse_json_payload(payload)
                    if data:
                        if data.get("productid"):
                            self.product_id = data["productid"]
                        self.last_data.update(data)
                        self._save_cache()
                        _log.info(
                            "<-- TELEMETRIA [%s]: mode=%s spd=%s flw=%s/%s m3/h T_out=%s°C T_in=%s°C",
                            self.product_id,
                            self.last_data.get("current_mode"),
                            self.last_data.get("set_spd"),
                            self.last_data.get("extf_flw"),
                            self.last_data.get("ffe_flw"),
                            self.last_data.get("outside_tpt"),
                            self.last_data.get("ext_tpt"),
                        )
                        _log.info(self.last_data)
                        self.publish_telemetry(self.last_data)
                elif ptype == mqtt.PT_PUBREL:
                    pid = struct.unpack_from(">H", body)[0] if len(body) >= 2 else 0
                    sock.sendall(mqtt.build_pubcomp(pid))
                elif ptype == mqtt.PT_DISCONNECT:
                    break
        except Exception as exc:
            _log.warning("Connessione Box chiusa: %s", exc)
        finally:
            with self.box_lock:
                if self.box_sock is sock:
                    self.box_sock = None
                    self.box_connected = False
                    self._ha_pub(f"{self.prefix}/health/box_connected", "false")
            try:
                sock.close()
            except Exception:
                pass

    def _ha_pub(self, topic, payload, retain=True):
        with self.ha_lock:
            if not self.ha_sock:
                return
            self.ha_pkt_id = (self.ha_pkt_id % 65530) + 1
            try:
                self.ha_sock.sendall(
                    mqtt.build_publish(topic, str(payload), qos=1, pkt_id=self.ha_pkt_id, retain=retain)
                )
            except Exception:
                pass

    def publish_discovery(self):
        dev = {
            "identifiers": ["aldes_inspirair_sc150"],
            "name": "Aldes InspirAIR Home SC150",
            "manufacturer": "Aldes",
            "model": "InspirAIR Home SC150",
        }
        if self.last_data.get("Vers_UC") or self.last_data.get("Vers_W"):
            dev["sw_version"] = f"UC {self.last_data.get('Vers_UC', '?')} / Wi-Fi {self.last_data.get('Vers_W', '?')}"

        # Rimozione automatica eventuali entita residue della vecchia T.ONE
        old_topics = [
            "homeassistant/climate/aldes/config",
            "homeassistant/water_heater/aldes_ballon/config",
            "homeassistant/number/aldes_people/config",
            "homeassistant/date/vacation_start/config",
            "homeassistant/date/vacation_end/config",
            "homeassistant/switch/vacation_enable/config",
        ]
        for ot in old_topics:
            self._ha_pub(ot, "")

        # 1. Entita FAN nativa Home Assistant
        fan_cfg = {
            "name": "VMC InspirAIR SC150",
            "unique_id": "aldes_sc150_fan",
            "device": dev,
            "state_topic": f"{self.prefix}/state/fan/state",
            "command_topic": f"{self.prefix}/set/fan/state",
            "payload_on": "ON",
            "payload_off": "OFF",
            "percentage_state_topic": f"{self.prefix}/state/fan/speed",
            "percentage_command_topic": f"{self.prefix}/set/fan/speed",
            "speed_range_min": 1,
            "speed_range_max": 3,
            "preset_modes": list(VMC_CODE_TO_PRESET.values()),
            "preset_mode_state_topic": f"{self.prefix}/state/fan/preset",
            "preset_mode_command_topic": f"{self.prefix}/set/fan/preset",
            "availability_topic": f"{self.prefix}/state/available",
            "icon": "mdi:fan",
        }
        self._ha_pub("homeassistant/fan/aldes_sc150/config", json.dumps(fan_cfg, ensure_ascii=False))

        # 2. Pulsanti test modalita V, X, Y, Z
        buttons = [
            ("mode_v", "Modalita Quotidiano (Codice V)", "mdi:home-clock"),
            ("mode_x", "Test Modalita X (Boost / Ospiti)", "mdi:fan-chevron-up"),
            ("mode_y", "Test Modalita Y (Ospiti / Boost)", "mdi:account-multiple-plus"),
            ("mode_z", "Modalita Programmazione (Codice Z)", "mdi:calendar-clock"),
        ]
        for bid, bname, bicon in buttons:
            bcfg = {
                "name": bname,
                "unique_id": f"aldes_sc150_btn_{bid}",
                "command_topic": f"{self.prefix}/set/button/{bid}",
                "payload_press": "PRESS",
                "device": dev,
                "icon": bicon,
                "availability_topic": f"{self.prefix}/state/available",
            }
            self._ha_pub(f"homeassistant/button/aldes_sc150_{bid}/config", json.dumps(bcfg, ensure_ascii=False))

        # 3. Sensori telemetria SC150 (15 attivi + 8 a zero disabilitati di default)
        for suf, key, name, unit, dclass, sclass, icon, en, _ in SENSORS:
            scfg = {
                "name": name,
                "unique_id": f"aldes_sc150_{suf}",
                "state_topic": f"{self.prefix}/state/sensor/{key}",
                "device": dev,
                "icon": icon,
                "enabled_by_default": en,
                "availability_topic": f"{self.prefix}/state/available",
            }
            if unit:
                scfg["unit_of_measurement"] = unit
            if dclass:
                scfg["device_class"] = dclass
            if sclass:
                scfg["state_class"] = sclass
            self._ha_pub(f"homeassistant/sensor/sc150_{suf}/config", json.dumps(scfg, ensure_ascii=False))

        # 4. Binary sensor stato connessione Box
        bconn = {
            "name": "Connessione Connect Box",
            "unique_id": "aldes_sc150_box_connected",
            "state_topic": f"{self.prefix}/health/box_connected",
            "payload_on": "true",
            "payload_off": "false",
            "device_class": "connectivity",
            "device": dev,
            "icon": "mdi:router-wireless",
            "availability_topic": f"{self.prefix}/state/available",
        }
        self._ha_pub("homeassistant/binary_sensor/sc150_box_connected/config", json.dumps(bconn, ensure_ascii=False))

        self._ha_pub(f"{self.prefix}/state/available", "online")
        self._ha_pub(f"{self.prefix}/health/box_connected", "true" if self.box_connected else "false")

    def publish_telemetry(self, data):
        for _, key, _, _, _, _, _, _, is_float in SENSORS:
            if key in data and data[key] is not None:
                val = data[key]
                if is_float is True:
                    try:
                        val = f"{float(val):.1f}"
                    except Exception:
                        pass
                elif is_float is False:
                    try:
                        val = f"{int(round(float(val)))}"
                    except Exception:
                        pass
                self._ha_pub(f"{self.prefix}/state/sensor/{key}", str(val).strip())

        self._ha_pub(f"{self.prefix}/state/fan/state", "ON")
        cm = str(data.get("current_mode") or "").strip().upper()
        if cm:
            self._ha_pub(f"{self.prefix}/state/fan/preset", VMC_CODE_TO_PRESET.get(cm, cm))
        if "set_spd" in data and data["set_spd"] is not None:
            try:
                spd = max(1, min(3, int(round(float(data["set_spd"])))))
                self._ha_pub(f"{self.prefix}/state/fan/speed", {1: "33", 2: "66", 3: "100"}[spd])
            except Exception:
                pass

    def _apply_mode(self, code):
        code = code.strip().upper()
        if code == "W":
            now_s = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%SZ")
            end_s = datetime.fromtimestamp(time.time() + 7 * 86400, tz=timezone.utc).strftime("%Y%m%d%H%M%SZ")
            self.send_to_box("changeMode", ["W", now_s, end_s])
        else:
            self.send_to_box("changeMode", [code])
        self._ha_pub(f"{self.prefix}/state/fan/preset", VMC_CODE_TO_PRESET.get(code, code))
        self._ha_pub(f"{self.prefix}/state/sensor/current_mode", code)
        self._ha_pub(f"{self.prefix}/state/fan/state", "ON")

    def _handle_ha_cmd(self, topic, payload):
        p = payload.strip()
        _log.info("Comando ricevuto da HA [%s]: %s", topic, p)
        if topic.endswith("/button/mode_v") or topic.endswith("/fan/state"):
            self._apply_mode("V")
        elif topic.endswith("/button/mode_x"):
            self._apply_mode("X")
        elif topic.endswith("/button/mode_y"):
            self._apply_mode("Y")
        elif topic.endswith("/button/mode_z"):
            self._apply_mode("Z")
        elif topic.endswith("/fan/preset"):
            code = VMC_PRESET_TO_CODE.get(p.lower())
            if code:
                self._apply_mode(code)
        elif topic.endswith("/fan/speed"):
            try:
                v = float(p)
                code, pct = ("V", "33") if v <= 34 else (("Y", "66") if v <= 67 else ("X", "100"))
                self._apply_mode(code)
                self._ha_pub(f"{self.prefix}/state/fan/speed", pct)
            except ValueError:
                pass

    def run_ha_mqtt(self):
        host, port, user, pw = detect_mqtt_broker()
        while True:
            try:
                _log.info("Connessione a Mosquitto (%s:%d, user=%s)...", host, port, user or "nessuno")
                s = socket.create_connection((host, port), timeout=6)
                s.settimeout(15)
                reader = mqtt.MQTTReader(s)
                s.sendall(
                    mqtt.build_connect(
                        "aldes-sc150-bridge",
                        username=user,
                        password=pw,
                        keepalive=30,
                        will_topic=f"{self.prefix}/state/available",
                        will_payload="offline",
                        will_qos=1,
                        will_retain=True,
                    )
                )
                pkt = reader.read_packet()
                if not pkt or pkt[0] != mqtt.PT_CONNACK or (len(pkt[3]) > 2 and pkt[3][2] != 0):
                    rc = pkt[3][2] if (pkt and len(pkt[3]) > 2) else -1
                    _log.error("CONNACK rifiutato da Mosquitto (rc=%d). Verifica utente/password MQTT.", rc)
                    s.close()
                    time.sleep(5)
                    continue
                with self.ha_lock:
                    self.ha_sock = s
                s.sendall(mqtt.build_subscribe(1, [(f"{self.prefix}/set/#", 1)]))
                self.publish_discovery()
                if self.last_data:
                    self.publish_telemetry(self.last_data)
                _log.info("Connesso a Mosquitto: Auto-Discovery SC150 pubblicata!")
                last_ping = time.time()
                while True:
                    try:
                        pkt = reader.read_packet()
                    except socket.timeout:
                        if time.time() - last_ping >= 15:
                            with self.ha_lock:
                                s.sendall(mqtt.build_pingreq())
                            last_ping = time.time()
                        continue
                    if pkt is None:
                        break
                    ptype, flags, body, _ = pkt
                    if ptype == mqtt.PT_PUBLISH:
                        t, qos, pid, pl = mqtt.parse_publish_full(body, flags)
                        if qos == 1:
                            with self.ha_lock:
                                s.sendall(mqtt.build_puback(pid))
                        self._handle_ha_cmd(t, pl.decode("utf-8", errors="replace"))
            except Exception as exc:
                _log.warning("Disconnesso da Mosquitto (%s), nuovo tentativo tra 5s...", exc)
            finally:
                with self.ha_lock:
                    self.ha_sock = None
            time.sleep(5)


def main():
    port = int(os.environ.get("MQTT_PORT", "18883"))
    bridge = SC150Bridge(listen_port=port)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    threading.Thread(target=bridge.run_box_listener, daemon=True).start()
    bridge.run_ha_mqtt()


if __name__ == "__main__":
    main()