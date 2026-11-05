"""Generazione e invio dei messaggi di Auto-Discovery MQTT per Home Assistant.

Questo modulo registra il dispositivo Aldes InspirAIR Home SC150 su Home Assistant
insieme a tutte le sue entita' (Select modalita', Pulsanti, Sensori telemetria e Sensori filtro).
"""
import json
from typing import TYPE_CHECKING

from .models import TELEMETRY_SENSORS

if TYPE_CHECKING:
    from .bridge import AldesBridge


def publish_homeassistant_discovery(bridge: "AldesBridge") -> None:
    """Pubblica su Mosquitto la configurazione di tutte le entita' di Home Assistant."""
    translations = bridge.translations
    prefix = bridge.config.mqtt_prefix

    device_info = {
        "identifiers": ["aldes_inspirair_sc150"],
        "name": translations.get("device_name", "Aldes InspirAIR Home SC150"),
        "manufacturer": "Aldes",
        "model": "InspirAIR Home SC150",
    }
    if bridge.last_telemetry.get("Vers_UC") or bridge.last_telemetry.get("Vers_W"):
        uc_ver = bridge.last_telemetry.get("Vers_UC", "?")
        wifi_ver = bridge.last_telemetry.get("Vers_W", "?")
        device_info["sw_version"] = f"UC {uc_ver} / Wi-Fi {wifi_ver}"

    # 1. Pulizia automatica di vecchie entita' non piu' utilizzate
    obsolete_discovery_topics = [
        "homeassistant/climate/aldes/config",
        "homeassistant/water_heater/aldes_ballon/config",
        "homeassistant/fan/aldes_sc150/config",
        "homeassistant/number/aldes_people/config",
        "homeassistant/button/aldes_sc150_mode_z/config",
    ]
    for old_topic in obsolete_discovery_topics:
        bridge.publish_to_ha(old_topic, "")

    # 2. Entita' SELECT principale per cambiare la modalita' della VMC (V, Y, X, W)
    select_config = {
        "name": translations.get("select_mode_name", "Modalit\u00e0 VMC"),
        "unique_id": "aldes_sc150_mode_select",
        "device": device_info,
        "state_topic": f"{prefix}/state/select/mode",
        "command_topic": f"{prefix}/set/select/mode",
        "options": list(bridge.exposed_modes.values()),
        "availability_topic": f"{prefix}/state/available",
        "icon": "mdi:air-filter",
    }
    bridge.publish_to_ha(
        "homeassistant/select/aldes_sc150_mode/config",
        json.dumps(select_config, ensure_ascii=False),
    )

    # 3. Pulsanti rapidi per forzare l'invio di una modalita'
    button_translations = translations.get("buttons", {})
    mode_buttons = [
        ("mode_v", button_translations.get("mode_v", "Modalit\u00e0 Quotidiano (V)"), "mdi:home-clock"),
        ("mode_y", button_translations.get("mode_y", "Modalit\u00e0 Cucina (Y)"), "mdi:silverware-fork-knife"),
        ("mode_x", button_translations.get("mode_x", "Modalit\u00e0 Boost (X)"), "mdi:fan-chevron-up"),
        ("mode_w", button_translations.get("mode_w", "Modalit\u00e0 Vacanze (W)"), "mdi:beach"),
    ]
    for button_id, button_name, button_icon in mode_buttons:
        button_config = {
            "name": button_name,
            "unique_id": f"aldes_sc150_btn_{button_id}",
            "command_topic": f"{prefix}/set/button/{button_id}",
            "payload_press": "PRESS",
            "device": device_info,
            "icon": button_icon,
            "availability_topic": f"{prefix}/state/available",
        }
        bridge.publish_to_ha(
            f"homeassistant/button/aldes_sc150_{button_id}/config",
            json.dumps(button_config, ensure_ascii=False),
        )

    # 4. Sensori di telemetria standard definiti in server/models.py
    sensor_translations = translations.get("sensors", {})
    for sensor in TELEMETRY_SENSORS:
        discovery_topic = f"homeassistant/sensor/sc150_{sensor.sensor_id}/config"
        if not sensor.is_active:
            # Se il sensore e' disattivato (es. RSSI), invia stringa vuota per rimuoverlo da HA
            bridge.publish_to_ha(discovery_topic, "")
            continue

        sensor_config = {
            "name": sensor_translations.get(sensor.sensor_id, sensor.sensor_id),
            "unique_id": f"aldes_sc150_{sensor.sensor_id}",
            "state_topic": f"{prefix}/state/sensor/{sensor.telemetry_key}",
            "device": device_info,
            "icon": sensor.icon,
            "enabled_by_default": sensor.enabled_by_default,
            "availability_topic": f"{prefix}/state/available",
        }
        if sensor.unit:
            sensor_config["unit_of_measurement"] = sensor.unit
        if sensor.device_class:
            sensor_config["device_class"] = sensor.device_class
        if sensor.state_class:
            sensor_config["state_class"] = sensor.state_class

        bridge.publish_to_ha(discovery_topic, json.dumps(sensor_config, ensure_ascii=False))

    # 5. Sensori calcolati dal modulo FilterTracker (server/filters.py)
    filter_sensors = [
        (
            "filter_remaining_days",
            sensor_translations.get("filter_remaining_days", "Giorni Residui Filtro"),
            "d",
            None,
            "measurement",
            "mdi:calendar-clock",
        ),
        (
            "filter_elapsed_days",
            sensor_translations.get("filter_elapsed_days", "Giorni Utilizzo Filtro"),
            "d",
            None,
            "measurement",
            "mdi:calendar-check",
        ),
        (
            "filter_wear_percent",
            sensor_translations.get("filter_wear_percent", "Usura Stimata Filtro"),
            "%",
            None,
            "measurement",
            "mdi:air-filter",
        ),
        (
            "filter_last_reset",
            sensor_translations.get("filter_last_reset", "Ultimo Reset Filtro"),
            None,
            "timestamp",
            None,
            "mdi:history",
        ),
    ]
    for f_id, f_name, f_unit, f_dclass, f_sclass, f_icon in filter_sensors:
        f_cfg = {
            "name": f_name,
            "unique_id": f"aldes_sc150_{f_id}",
            "state_topic": f"{prefix}/state/filter/{f_id}",
            "device": device_info,
            "icon": f_icon,
            "availability_topic": f"{prefix}/state/available",
        }
        if f_unit:
            f_cfg["unit_of_measurement"] = f_unit
        if f_dclass:
            f_cfg["device_class"] = f_dclass
        if f_sclass:
            f_cfg["state_class"] = f_sclass
        bridge.publish_to_ha(
            f"homeassistant/sensor/sc150_{f_id}/config",
            json.dumps(f_cfg, ensure_ascii=False),
        )

    # 6. Sensore binario per lo stato di connessione della Aldes Connect Box
    connectivity_config = {
        "name": translations.get("box_connected_name", "Connessione Connect Box"),
        "unique_id": "aldes_sc150_box_connected",
        "state_topic": f"{prefix}/health/box_connected",
        "payload_on": "true",
        "payload_off": "false",
        "device_class": "connectivity",
        "device": device_info,
        "icon": "mdi:router-wireless",
        "availability_topic": f"{prefix}/state/available",
    }
    bridge.publish_to_ha(
        "homeassistant/binary_sensor/sc150_box_connected/config",
        json.dumps(connectivity_config, ensure_ascii=False),
    )

    # Pubblica lo stato iniziale di disponibilita'
    bridge.publish_to_ha(f"{prefix}/state/available", "online")
    bridge.publish_to_ha(f"{prefix}/health/box_connected", "true" if bridge.box_connected else "false")