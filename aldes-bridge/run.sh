#!/bin/bash
export MQTT_PORT=18883
export ALDES_LANG="it"
BOX_IP=""

if [ -f /data/options.json ]; then
  export MQTT_PORT=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('mqtt_port', 18883))")
  export ALDES_LANG=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('language', 'it') or 'it')")
  BOX_IP=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('box_ip', ''))")
  export HA_MQTT_HOST=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_host', ''))")
  export HA_MQTT_PORT=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_port', 1883))")
  export HA_MQTT_USER=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_user', ''))")
  export HA_MQTT_PASSWORD=$(python3 -c "import json; d=json.load(open('/data/options.json')); print(d.get('ha_mqtt_password', ''))")
fi

if [ "$MQTT_PORT" != "8883" ]; then
  for chain in PREROUTING OUTPUT; do
    i=0; while [ $i -lt 20 ] && iptables -t nat -D "$chain" -p tcp --dport 8883 -j REDIRECT --to-port "$MQTT_PORT" 2>/dev/null; do i=$((i+1)); done
  done
  if [ -n "$BOX_IP" ]; then
    iptables -t nat -I PREROUTING 1 -p tcp -s "$BOX_IP" --dport 8883 -j REDIRECT --to-port "$MQTT_PORT"
    echo "[run.sh] iptables PREROUTING: 8883 -> $MQTT_PORT (solo da $BOX_IP)"
  else
    iptables -t nat -I PREROUTING 1 -p tcp --dport 8883 -j REDIRECT --to-port "$MQTT_PORT"
    echo "[run.sh] iptables PREROUTING: 8883 -> $MQTT_PORT (tutte le sorgenti)"
  fi
fi

mkdir -p /config/aldes
exec python3 -m server.main