"""Client MQTT pour la discovery HA et le publishing des données PAC et VMC."""
import json
import logging
import socket
import struct
import threading
import time
from datetime import datetime, timezone

from .. import mqtt
from ..appstate import emit_message
from ..utils import safe_float
from .mode_mappings import (
    ALDES_TO_HA_MODE, HA_MODE_TO_ALDES,
    ALDES_TO_HA_PRESET, HA_PRESET_TO_ALDES,
    ALDES_WATER_TO_HA, HA_WATER_TO_ALDES,
    profile_code_for_label, profile_label_for_code,
)
from .discovery_config import (
    build_discovery_config,
    detect_active_zones,
    is_vmc_device,
)

_log = logging.getLogger("aldes-ha-discovery")

_VMC_CODE_TO_PRESET = {
    "V": "Quotidiano (V)",
    "X": "Modalità X",
    "Y": "Modalità Y",
    "W": "Vacanze (W)",
    "Z": "Programmazione (Z)",
}

_VMC_PRESET_TO_CODE = {v.casefold(): k for k, v in _VMC_CODE_TO_PRESET.items()}
_VMC_PRESET_TO_CODE.update({
    "v": "V", "quotidiano": "V",
    "x": "X", "boost": "X",
    "y": "Y", "ospiti": "Y",
    "w": "W", "vacanze": "W",
    "z": "Z", "programmazione": "Z",
})

_VMC_FLOAT_KEYS = ("outside_tpt", "ext_tpt", "reject_tpt", "Co2_vmc", "Pm25_Vmc")
_VMC_INT_KEYS = (
    "extf_flw", "ffe_flw", "extf_spd", "vi_spd", "set_spd",
    "ff_cpt", "dep_ind", "dtb_ind", "cve_csn", "vi_csn",
    "tte_csn", "echange_pwr", "Voc_Vmc", "Vers_UC",
)
_VMC_STR_KEYS = ("current_mode", "RSSI", "Vers_W")


class HADiscoveryClient(threading.Thread):
    """Client MQTT qui connecte au broker local pour publier la decouverte HA."""

    KEEPALIVE = 30
    PUBLISH_INTERVAL = 60

    def __init__(self, state, host="127.0.0.1", port=1883, username=None, password=None, prefix="aldes", dry_run=True, zones_file=None):
        super().__init__(daemon=True, name="ha-discovery")
        self.state = state
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.prefix = prefix
        self.dry_run = dry_run
        self._stop = threading.Event()
        self._sock = None
        self._send_lock = threading.Lock()
        self._pkt = 0
        self._device_id = "aldes_bridge"
        self._last_mode = None
        self._vmc_discovery_sent = False
        self._zones_file = zones_file
        self._last_active_zones = self._load_zones()
        if dry_run:
            _log.warning("ha-discovery: *** DRY-RUN active *** les commandes HA ne seront PAS envoyees a la box")

    def _load_zones(self):
        if not self._zones_file:
            return []
        try:
            with open(self._zones_file, "r") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_zones(self, zones):
        if not self._zones_file:
            return
        try:
            with open(self._zones_file, "w") as f:
                json.dump(zones, f)
        except OSError as exc:
            _log.warning("ha-discovery: impossible de sauvegarder les zones: %s", exc)

    def stop(self):
        self._stop.set()
        with self._send_lock:
            sock = self._sock
            self._sock = None
        if sock:
            try:
                sock.close()
            except Exception:
                pass

    def run(self):
        backoff = 1.0
        try:
            while not self._stop.is_set():
                ok = self._session()
                backoff = 1.0 if ok else min(backoff * 2, 10)
                if not self._stop.is_set():
                    time.sleep(backoff)
        except Exception as exc:
            _log.exception("ha-discovery: thread crashed: %s", exc)

    def _session(self):
        _log.info("ha-discovery: tentative connexion vers %s:%d (user=%s)",
                  self.host, self.port, self.username or "(none)")
        try:
            s = socket.create_connection((self.host, self.port), timeout=6)
            s.settimeout(self.KEEPALIVE / 3)
        except Exception as exc:
            _log.warning("ha-discovery: connexion impossible vers %s:%d: %s", self.host, self.port, exc)
            return False

        reader = mqtt.MQTTReader(s)
        try:
            s.sendall(mqtt.build_connect(
                "aldes-ha-discovery",
                username=self.username,
                password=self.password,
                keepalive=self.KEEPALIVE,
                will_topic=f"{self.prefix}/state/available",
                will_payload="offline",
                will_qos=1,
                will_retain=True,
            ))
            pkt = reader.read_packet()
            if pkt is None or pkt[0] != mqtt.PT_CONNACK or (pkt[3][2] if len(pkt[3]) > 2 else -1) != 0:
                rc = pkt[3][2] if pkt and len(pkt[3]) > 2 else -1
                _log.warning("ha-discovery: CONNACK refuse (rc=%d) — broker=%s:%d", rc, self.host, self.port)
                s.close()
                return False
            _log.info("ha-discovery: CONNACK OK — connecte a %s:%d", self.host, self.port)
        except Exception as exc:
            _log.warning("ha-discovery: erreur handshake: %s", exc)
            try:
                s.close()
            except Exception:
                pass
            return False

        self._sock = s

        cmd_topics = [
            (f"{self.prefix}/set/mode", 1),
            (f"{self.prefix}/set/consigne", 1),
            (f"{self.prefix}/set/preset", 1),
            (f"{self.prefix}/set/ecs", 1),
            (f"{self.prefix}/set/vacation_start", 1),
            (f"{self.prefix}/set/vacation_end", 1),
            (f"{self.prefix}/set/vacation_enable", 1),
            (f"{self.prefix}/set/people", 1),
            (f"{self.prefix}/set/fan/state", 1),
            (f"{self.prefix}/set/fan/preset", 1),
            (f"{self.prefix}/set/fan/speed", 1),
            (f"{self.prefix}/set/button/mode_v", 1),
            (f"{self.prefix}/set/button/mode_x", 1),
            (f"{self.prefix}/set/button/mode_y", 1),
            (f"{self.prefix}/set/button/mode_z", 1),
        ]
        for zi in range(10):
            cmd_topics.append((f"{self.prefix}/set/zone{zi}/consigne", 1))
        topic_list = [t for t, _ in cmd_topics]
        _log.info("ha-discovery: souscription a %d topics: %s", len(topic_list), topic_list)
        try:
            s.sendall(mqtt.build_subscribe(1, cmd_topics))
        except Exception as exc:
            _log.warning("ha-discovery: subscribe echoue: %s", exc)
            s.close()
            return False

        try:
            suback = reader.read_packet()
            if suback and suback[0] == mqtt.PT_SUBACK:
                _log.info("ha-discovery: SUBACK recu — souscription OK")
            else:
                _log.warning("ha-discovery: pas de SUBACK (recu: %s)", suback)
        except Exception as exc:
            _log.warning("ha-discovery: erreur SUBACK: %s", exc)

        self._publish_discovery()
        self._publish_state()

        last_ping = time.time()
        last_config_publish = time.time()
        try:
            while not self._stop.is_set():
                try:
                    pkt = reader.read_packet()
                except socket.timeout:
                    if time.time() - last_ping >= self.KEEPALIVE / 2:
                        self._safe_send(mqtt.build_pingreq())
                        last_ping = time.time()
                    if time.time() - last_config_publish >= self.PUBLISH_INTERVAL:
                        self._publish_discovery()
                        self._publish_state()
                        last_config_publish = time.time()
                    continue
                except (mqtt.MQTTError, OSError):
                    break
                if pkt is None:
                    break
                self._handle(pkt)
        finally:
            self._teardown()
        return True

    def _handle(self, pkt):
        ptype, flags, body, raw = pkt
        if ptype == mqtt.PT_PUBLISH:
            topic, qos, pid, payload = mqtt.parse_publish_full(body, flags)
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8", errors="replace")
            _log.info("ha-discovery: <-- MQTT PUBLISH topic=%s payload=%s", topic, payload[:200])
            if qos == mqtt.QOS_AT_LEAST_ONCE:
                self._safe_send(mqtt.build_puback(pid))
            elif qos == mqtt.QOS_EXACTLY_ONCE:
                self._safe_send(mqtt.build_pubrec(pid))
            self._handle_command(topic, payload)
        elif ptype == mqtt.PT_PUBREC:
            pid = struct.unpack_from(">H", body, 0)[0]
            self._safe_send(mqtt.build_pubrel(pid))
        elif ptype == mqtt.PT_SUBACK:
            _log.info("ha-discovery: <-- MQTT SUBACK")
        elif ptype in (mqtt.PT_PUBACK, mqtt.PT_PUBCOMP):
            pass

    def _handle_command(self, topic, payload):
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")
        payload = payload.strip()
        _log.info("ha-discovery: COMMANDE RECUE topic=%s payload=%s", topic, payload)

        try:
            if topic == f"{self.prefix}/set/mode":
                self._handle_mode_command(payload)
            elif topic == f"{self.prefix}/set/consigne":
                self._handle_consigne_command(payload, zone=0)
            elif topic.startswith(f"{self.prefix}/set/zone") and topic.endswith("/consigne"):
                zone_str = topic.split("/set/zone")[1].split("/")[0]
                try:
                    zone = int(zone_str)
                except ValueError:
                    zone = 0
                self._handle_consigne_command(payload, zone=zone)
            elif topic == f"{self.prefix}/set/preset":
                self._handle_preset_command(payload)
            elif topic == f"{self.prefix}/set/ecs":
                self._handle_ecs_command(payload)
            elif topic == f"{self.prefix}/set/vacation_start":
                self._handle_vacation_start_command(payload)
            elif topic == f"{self.prefix}/set/vacation_end":
                self._handle_vacation_end_command(payload)
            elif topic == f"{self.prefix}/set/vacation_enable":
                self._handle_vacation_enable_command(payload)
            elif topic == f"{self.prefix}/set/people":
                self._handle_people_command(payload)
            elif topic == f"{self.prefix}/set/fan/state":
                self._handle_vmc_fan_state_command(payload)
            elif topic == f"{self.prefix}/set/fan/preset":
                self._handle_vmc_preset_command(payload)
            elif topic == f"{self.prefix}/set/fan/speed":
                self._handle_vmc_speed_command(payload)
            elif topic == f"{self.prefix}/set/button/mode_v":
                self._send_vmc_mode("V")
            elif topic == f"{self.prefix}/set/button/mode_x":
                self._send_vmc_mode("X")
            elif topic == f"{self.prefix}/set/button/mode_y":
                self._send_vmc_mode("Y")
            elif topic == f"{self.prefix}/set/button/mode_z":
                self._send_vmc_mode("Z")
        except Exception as exc:
            _log.warning("ha-discovery: erreur commande %s: %s", topic, exc)

    def _send_vmc_mode(self, code):
        code = code.strip().upper()
        if code == "W":
            now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%SZ")
            end_ts = time.time() + 7 * 86400
            end_str = datetime.fromtimestamp(end_ts, tz=timezone.utc).strftime("%Y%m%d%H%M%SZ")
            self._inject_aldes_command("changeMode", ["W", now_str, end_str])
        else:
            self._inject_aldes_command("changeMode", [code])
        preset_label = _VMC_CODE_TO_PRESET.get(code, code)
        self._safe_send(mqtt.build_publish(
            f"{self.prefix}/state/fan/preset", preset_label, qos=1, retain=True
        ))
        self._safe_send(mqtt.build_publish(
            f"{self.prefix}/state/sensor/current_mode", code, qos=1, retain=True
        ))
        self._safe_send(mqtt.build_publish(
            f"{self.prefix}/state/fan/state", "ON", qos=1, retain=True
        ))

    def _handle_vmc_fan_state_command(self, payload):
        self._send_vmc_mode("V")

    def _handle_vmc_preset_command(self, payload):
        code = _VMC_PRESET_TO_CODE.get(payload.strip().casefold())
        if code:
            self._send_vmc_mode(code)

    def _handle_vmc_speed_command(self, payload):
        try:
            val = float(payload)
        except ValueError:
            return
        if val <= 1 or val <= 34:
            code, spd_pct = "V", "33"
        elif val <= 67:
            code, spd_pct = "Y", "66"
        else:
            code, spd_pct = "X", "100"
        self._send_vmc_mode(code)
        self._safe_send(mqtt.build_publish(
            f"{self.prefix}/state/fan/speed", spd_pct, qos=1, retain=True
        ))

    def _handle_mode_command(self, payload):
        ha_mode = payload.lower().strip()
        aldes_code = HA_MODE_TO_ALDES.get(ha_mode)
        if aldes_code:
            self._inject_aldes_command("changeMode", [aldes_code])

    def _handle_consigne_command(self, payload, zone=0):
        try:
            temp = float(payload)
        except ValueError:
            return
        self._inject_aldes_command(f"changeConsigneC{zone}", [str(temp)])
        self.state.request_consigne(str(zone), temp)

    def _handle_preset_command(self, payload):
        preset = payload.strip()
        profile = getattr(self.state, "profile", None)
        aldes_code = profile_code_for_label(profile, ["air_modes_clim", "air_modes_heat"], preset, HA_PRESET_TO_ALDES)
        if aldes_code:
            self._inject_aldes_command("changeMode", [aldes_code])

    def _handle_ecs_command(self, payload):
        mode = payload.strip()
        profile = getattr(self.state, "profile", None)
        aldes_code = profile_code_for_label(profile, "water_modes", mode, HA_WATER_TO_ALDES)
        if aldes_code:
            self._inject_aldes_command("changeMode", [aldes_code])

    def _handle_vacation_start_command(self, payload):
        pass

    def _handle_vacation_end_command(self, payload):
        pass

    def _handle_vacation_enable_command(self, payload):
        pass

    def _handle_people_command(self, payload):
        pass

    def _resolve_devicebound_topic(self):
        if self.state:
            with self.state._lock:
                topics = sorted(self.state._topics)
                client_id = self.state._client_id
                telemetry = dict(self.state.telemetry)
            for t in topics:
                if "devicebound" in t:
                    return t.split("/#")[0].rstrip("/")
            if telemetry:
                first_data = next(iter(telemetry.values()), {})
                pid = first_data.get("productid") or first_data.get("_pid")
                if pid:
                    return f"devices/{pid}/messages/devicebound"
            if client_id:
                return f"devices/{client_id}/messages/devicebound"
        return f"devices/{self._device_id}/messages/devicebound"

    def _inject_aldes_command(self, method, params):
        body = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": method,
            "params": params if isinstance(params, list) else [params],
        }
        dry_run = self.state.config.get("ha_mqtt_dry_run") if self.state.config else self.dry_run
        if dry_run:
            _log.info("ha-discovery [DRY-RUN]: commande simulée: %s", json.dumps(body, ensure_ascii=False))
            return
        hook = getattr(self.state, "_ha_inject_hook", None)
        if hook:
            hook(self._resolve_devicebound_topic(), json.dumps(body, ensure_ascii=False), 1)

    def _publish_discovery(self):
        with self.state._lock:
            telemetry = dict(self.state.telemetry)
        data = next(iter(telemetry.values()), {}) if telemetry else None
        profile = getattr(self.state, "profile", None)
        active_zones = detect_active_zones(data) if data else []
        zone_sensors = self.state.config.get("ha_zone_sensors") if self.state.config else False
        configs = build_discovery_config(
            self._device_id, profile, self.prefix, data,
            previous_active_zones=self._last_active_zones,
            zone_sensors=zone_sensors,
        )
        for topic, payload in configs:
            self._safe_send(mqtt.build_publish(topic, payload, qos=1, retain=True))
        if is_vmc_device(profile, data):
            self._vmc_discovery_sent = True
        self._last_active_zones = active_zones
        self._save_zones(active_zones)

    def _publish_state(self):
        with self.state._lock:
            telemetry = dict(self.state.telemetry)
            connected = self.state._connected

        availability = "online" if connected else "offline"
        self._safe_send(mqtt.build_publish(
            f"{self.prefix}/state/available", availability, qos=1, retain=True
        ))
        self._publish_health()
        if telemetry:
            data = next(iter(telemetry.values()), {})
            if data:
                self._publish_telemetry_data(data)

    def _publish_health(self):
        with self.state._lock:
            box_connected = self.state._connected
            start_time = self.state._start_time
        mqtt_connected = self._sock is not None
        uptime = time.time() - start_time
        status = "ok" if box_connected else ("degraded" if mqtt_connected is False else "ok")
        self._safe_send(mqtt.build_publish(f"{self.prefix}/health/status", status, qos=1, retain=True))
        self._safe_send(mqtt.build_publish(f"{self.prefix}/health/uptime", str(round(uptime, 1)), qos=1, retain=True))
        self._safe_send(mqtt.build_publish(f"{self.prefix}/health/mqtt_connected", str(mqtt_connected).lower(), qos=1, retain=True))
        self._safe_send(mqtt.build_publish(f"{self.prefix}/health/box_connected", str(box_connected).lower(), qos=1, retain=True))

    def publish_telemetry(self, data):
        if not self._sock:
            return
        profile = getattr(self.state, "profile", None)
        if is_vmc_device(profile, data) and not self._vmc_discovery_sent:
            self._publish_discovery()
        self._publish_telemetry_data(data)

    def _publish_vmc_telemetry_data(self, data):
        for key in _VMC_FLOAT_KEYS:
            val = safe_float(data.get(key))
            if val is not None:
                self._safe_send(mqtt.build_publish(f"{self.prefix}/state/sensor/{key}", f"{val:.1f}", qos=1, retain=True))
        for key in _VMC_INT_KEYS:
            val = safe_float(data.get(key))
            if val is not None:
                self._safe_send(mqtt.build_publish(f"{self.prefix}/state/sensor/{key}", f"{int(round(val))}", qos=1, retain=True))
        for key in _VMC_STR_KEYS:
            raw_val = data.get(key)
            if raw_val is not None:
                self._safe_send(mqtt.build_publish(f"{self.prefix}/state/sensor/{key}", str(raw_val).strip(), qos=1, retain=True))

        self._safe_send(mqtt.build_publish(f"{self.prefix}/state/fan/state", "ON", qos=1, retain=True))
        cur_mode = str(data.get("current_mode") or "").strip().upper()
        if cur_mode:
            preset_label = _VMC_CODE_TO_PRESET.get(cur_mode, cur_mode)
            self._safe_send(mqtt.build_publish(f"{self.prefix}/state/fan/preset", preset_label, qos=1, retain=True))
        spd = safe_float(data.get("set_spd"))
        if spd is not None:
            spd_int = max(1, min(3, int(round(spd))))
            pct_map = {1: "33", 2: "66", 3: "100"}
            self._safe_send(mqtt.build_publish(f"{self.prefix}/state/fan/speed", pct_map.get(spd_int, "33"), qos=1, retain=True))

    def _publish_telemetry_data(self, data, include_zone_aliases=False):
        profile = getattr(self.state, "profile", None)
        if is_vmc_device(profile, data):
            self._publish_vmc_telemetry_data(data)

        outdoor_temp = safe_float(data.get("Text"))
        if outdoor_temp is not None:
            self._safe_send(mqtt.build_publish(f"{self.prefix}/state/sensor/Text", f"{outdoor_temp:.1f}", qos=1, retain=True))

    def _safe_send(self, data):
        with self._send_lock:
            sock = self._sock
            if sock is None:
                return False
            try:
                sock.sendall(data)
                return True
            except (OSError, socket.timeout):
                return False

    def _teardown(self):
        with self._send_lock:
            self._sock = None