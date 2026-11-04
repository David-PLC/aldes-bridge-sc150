#!/bin/bash

OLD_DIR="/homeassistant/aldes"
NEW_DIR="/config/aldes"
MIGRATE_FLAG="$NEW_DIR/.migrated_from_ha"

if [ -d "$OLD_DIR" ] && [ ! -f "$MIGRATE_FLAG" ]; then
  if [ ! -d "$NEW_DIR" ] || [ -z "$(ls -A "$NEW_DIR" 2>/dev/null)" ]; then
    echo "[run.sh] Migration: copie des données depuis $OLD_DIR vers $NEW_DIR"
    mkdir -p "$NEW_DIR"
    cp -a "$OLD_DIR"/. "$NEW_DIR"/ 2>/dev/null || true
    touch "$MIGRATE_FLAG"
  else
    touch "$MIGRATE_FLAG"
  fi
fi

MQTT_PORT=18883
WEB_PORT=8080
BOX_IP=""
MODE="bridge"
PROFILE="inspirair-sc150"
HA_MQTT=""
DRY_RUN_ARG="--ha-mqtt-no-dry-run"

if [ -f /data/options.json ]; then
  val=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('mqtt_port',''))" 2>/dev/null)
  [ -n "$val" ] && MQTT_PORT=$val
  bip=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('box_ip',''))" 2>/dev/null)
  [ -n "$bip" ] && BOX_IP=$bip
  md=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('mode',''))" 2>/dev/null)
  [ -n "$md" ] && MODE=$md
  pf=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('profile','inspirair-sc150'))" 2>/dev/null)
  [ -n "$pf" ] && PROFILE=$pf
  ha=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(str(d.get('ha_mqtt_enabled','')).lower())" 2>/dev/null)
  [ "$ha" = "true" ] && HA_MQTT="--ha-mqtt"
  dr=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(str(d.get('ha_mqtt_dry_run','false')).lower())" 2>/dev/null)
  [ "$dr" = "true" ] && DRY_RUN_ARG="--ha-mqtt-dry-run"
  ha_user=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_user',''))" 2>/dev/null)
  ha_pass=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_password',''))" 2>/dev/null)
  ha_host=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_host',''))" 2>/dev/null)
  ha_port=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_port',''))" 2>/dev/null)
fi

if [ "$MQTT_PORT" != "8883" ]; then
  for chain in PREROUTING OUTPUT; do
    i=0; while [ $i -lt 20 ] && iptables -t nat -D "$chain" -p tcp --dport 8883 -j REDIRECT --to-port 18883 2>/dev/null; do i=$((i+1)); done
    i=0; while [ $i -lt 20 ] && iptables -t nat -D "$chain" -p tcp --dport 8883 -j REDIRECT --to-port 8080 2>/dev/null; do i=$((i+1)); done
    i=0; while [ $i -lt 20 ] && iptables -t nat -D "$chain" -p tcp -s "$BOX_IP" --dport 8883 -j REDIRECT --to-port 18883 2>/dev/null; do i=$((i+1)); done
  done

  if [ -n "$BOX_IP" ]; then
    iptables -t nat -I PREROUTING 1 -p tcp -s "$BOX_IP" --dport 8883 -j REDIRECT --to-port "$MQTT_PORT" 2>&1
  else
    iptables -t nat -I PREROUTING 1 -p tcp --dport 8883 -j REDIRECT --to-port "$MQTT_PORT" 2>&1
  fi
fi

mkdir -p /app/logs /config/aldes
echo "{\"mode\": \"$MODE\"}" > /app/logs/mode.json
echo "{\"profile_id\": \"$PROFILE\"}" > /config/aldes/profile.json

export HA_MQTT_USER="$ha_user"
export HA_MQTT_PASSWORD="$ha_pass"
HA_MQTT_HOST_ARG=""
HA_MQTT_PORT_ARG=""
[ -n "$ha_host" ] && HA_MQTT_HOST_ARG="--ha-mqtt-host $ha_host"
[ -n "$ha_port" ] && [ "$ha_port" != "1883" ] && HA_MQTT_PORT_ARG="--ha-mqtt-port $ha_port"

export ALDES_UI_VERSION=$(python3 -c "import json; d=json.load(open('/app/dist/version.json')); print(d.get('ui') or d.get('version') or '?')" 2>/dev/null || echo "?")

exec python3 -m server.main --mqtt-port "$MQTT_PORT" --web-port "$WEB_PORT" --mode "$MODE" --profile "$PROFILE" $HA_MQTT $DRY_RUN_ARG $HA_MQTT_HOST_ARG $HA_MQTT_PORT_ARG