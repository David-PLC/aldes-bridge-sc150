# Aldes Bridge SC150 — Home Assistant Add-on

![Version](https://img.shields.io/badge/version-2.2.2-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Arch](https://img.shields.io/badge/arch-amd64%20%7C%20aarch64-orange.svg)

**[Italiano](#italiano) | [English](#english)**

---

<a name="italiano"></a>
## Italiano

Add-on nativo per **Home Assistant** che consente il controllo **100% locale** e il monitoraggio completo della VMC **Aldes InspirAIR Home SC150** (tramite **Aldes Connect Box**), eliminando completamente la dipendenza dai server cloud Aldes.

> **Disclaimer / Esclusione di Responsabilità**
> Questo add-on è un progetto indipendente sviluppato a titolo amatoriale e open source. **L'autore non è in alcun modo affiliato, associato, autorizzato, sponsorizzato da, o ufficialmente collegato ad Aldes** (né ad alcuna delle sue consociate o affiliate).
> L'utilizzo di questo software avviene a vostro esclusivo rischio. L'autore non si assume alcuna responsabilità per eventuali malfunzionamenti, blocchi, perdite di dati o danneggiamenti alla VMC Aldes InspirAIR Home SC150, al modulo Aldes Connect Box, all'impianto elettrico/idraulico o all'installazione di Home Assistant derivanti dall'uso di questo add-on.

### Caratteristiche Principali

- **Controllo 100% Locale (Cloud-Free):** Intercetta il traffico MQTT over TLS (porta `8883` rediretta localmente su `18883`) che la Connect Box invia verso `aldesiotsuite.azure-devices.net`, gestendo telemetria e comandi direttamente nella rete locale.
- **Auto-Discovery MQTT Nativa:** Rileva automaticamente il broker Mosquitto di Home Assistant tramite le API del Supervisor e registra tutte le entità senza necessità di configurazione manuale in `configuration.yaml`.
- **Selettore Modalità Operativa (`select`):** Controllo diretto delle modalità supportate dalla VMC:
  * **Quotidiano (`V`)**
  * **Cucina (`Y`)**
  * **Boost (`X`)**
  * **Vacanze (`W`)** — con generazione automatica della finestra temporale concatenata in formato UTC (`W<inizio_UTC>Z<fine_UTC>Z`).
- **Verifica Comandi e Protezione Seriale:** Include un intervallo minimo di sicurezza (2 secondi) tra i pacchetti JSON-RPC per non saturare la comunicazione UART del modulo Wi-Fi (`HF-LPB100`) e un sistema di verifica automatica che reinvia il comando se la VMC non conferma il cambio modalità entro 15 secondi.
- **Stabilità Connessione (Grace Timer & Timeout Esteso):**
  * **Grace Timer (30s):** Maschera le micro-disconnessioni fisiologiche di ~5 secondi che la Connect Box effettua ogni 5 ore per il rinnovo del token di sessione, evitando falsi stati `Disconnesso` nello storico di Home Assistant.
  * **Timeout TLS a 660s:** Calibrato sull'intervallo di invio telemetria della macchina (10 minuti) per prevenire disconnessioni da timeout di lettura.
- **Monitoraggio Intelligente dei Filtri (`FilterTracker`):** Rileva automaticamente l'azzeramento del contatore `ff_cpt` effettuato dal display fisico della VMC dopo la sostituzione dei filtri, salvando la data su disco (`/config/aldes/filters.json`) e calcolando in autonomia giorni trascorsi, giorni residui e percentuale di usura.

### Prerequisito di Rete (DNS Locale)

La Aldes Connect Box tenta di collegarsi all'indirizzo cloud `aldesiotsuite.azure-devices.net` sulla porta TCP `8883`.
Per redirigere il traffico verso Home Assistant senza modificare fisicamente la Connect Box, è necessario configurare una regola di **DNS Rewrite** sul proprio server DNS locale (es. **AdGuard Home**, **Pi-hole**, **UniFi**, **MikroTik** o router compatibile):

```text
aldesiotsuite.azure-devices.net  --->  <INDIRIZZO_IP_HOME_ASSISTANT>
```

All'avvio, l'add-on applica automaticamente una regola `iptables` (`PREROUTING`) che inoltra i pacchetti in arrivo sulla porta `8883` verso la porta interna `18883` del bridge TLS.

### Installazione su Home Assistant

1. In Home Assistant, vai su **Impostazioni** → **Componenti aggiuntivi** → **Raccolta di componenti aggiuntivi**.
2. Clicca sui **tre puntini** in alto a destra e seleziona **Repository**.
3. Incolla l'URL di questo repository:
   ```text
   [https://github.com/David-PLC/aldes-bridge-sc150](https://github.com/David-PLC/aldes-bridge-sc150)
   ```
4. Clicca su **Aggiungi** e poi chiudi la finestra.
5. Cerca **Aldes Bridge SC150** nella lista dei componenti aggiuntivi, clicca su **Installa** e attiva le opzioni **Avvia all'avvio** e **Watchdog**.

### Configurazione

L'add-on funziona fin da subito con i valori predefiniti (rileva automaticamente il broker `core-mosquitto` di Home Assistant). Dalla scheda **Configurazione** dell'add-on è possibile personalizzare i seguenti parametri:

| Opzione | Default | Descrizione |
| :--- | :---: | :--- |
| `mqtt_port` | `18883` | Porta locale su cui il server TLS ascolta la Connect Box (redirige `8883` → `18883`). |
| `box_ip` | `""` | *(Opzionale)* Indirizzo IP della Connect Box per limitare la regola `iptables` solo al traffico proveniente dalla VMC. |
| `filter_months` | `6` | Durata nominale dei filtri in mesi (`6` mesi = 180 giorni) utilizzata per il calcolo dei giorni residui. |
| `language` | `"it"` | Lingua utilizzata per i nomi delle entità generate su Home Assistant (`translations/it.json`). |
| `ha_mqtt_host` | `""` | *(Opzionale)* Host del broker MQTT. Lasciare vuoto per il rilevamento automatico tramite Supervisor. |
| `ha_mqtt_port` | `1883` | Porta TCP del broker MQTT di Home Assistant. |
| `ha_mqtt_user` | `""` | *(Opzionale)* Nome utente MQTT (se non gestito automaticamente dal Supervisor). |
| `ha_mqtt_password` | `""` | *(Opzionale)* Password MQTT (se non gestita automaticamente dal Supervisor). |

### Entità Esposte su Home Assistant

#### Controllo e Stato Connessione
- `select.aldes_inspirair_home_sc150_modalita_vmc` — Selettore modalità (`Quotidiano`, `Cucina`, `Boost`, `Vacanze`)
- `binary_sensor.aldes_inspirair_home_sc150_connessione_connect_box` — Stato connessione TLS della Connect Box

#### Monitoraggio Filtri
- `sensor.aldes_inspirair_home_sc150_giorni_residui_filtro` — Giorni mancanti alla sostituzione del filtro
- `sensor.aldes_inspirair_home_sc150_giorni_utilizzo_filtro` — Giorni trascorsi dall'ultimo reset
- `sensor.aldes_inspirair_home_sc150_usura_stimata_filtro` — Percentuale di usura calcolata sulla durata impostata
- `sensor.aldes_inspirair_home_sc150_ultimo_reset_filtro` — Data e ora dell'ultimo cambio/reset filtro rilevato
- `sensor.aldes_inspirair_home_sc150_contatore_usura_filtro_box` — Contatore grezzo `ff_cpt` inviato dalla Connect Box
- `sensor.aldes_inspirair_home_sc150_indice_depressione_filtri` — Indice depressione (`dep_ind`)

#### Temperature, Portate e Ventilazione
- `sensor.aldes_inspirair_home_sc150_temperatura_aria_esterna` (`outside_tpt`, °C)
- `sensor.aldes_inspirair_home_sc150_temperatura_aria_estratta` (`ext_tpt`, °C)
- `sensor.aldes_inspirair_home_sc150_temperatura_aria_espulsa` (`reject_tpt`, °C)
- `sensor.aldes_inspirair_home_sc150_portata_estrazione` (`extf_flw`, m³/h)
- `sensor.aldes_inspirair_home_sc150_portata_insufflazione` (`ffe_flw`, m³/h)
- `sensor.aldes_inspirair_home_sc150_velocita_ventola_estrazione` (`extf_spd`, rpm)
- `sensor.aldes_inspirair_home_sc150_velocita_ventola_insufflazione` (`vi_spd`, rpm)
- `sensor.aldes_inspirair_home_sc150_livello_velocita_vmc` (`set_spd`)
- `sensor.aldes_inspirair_home_sc150_stato_bypass` (`dtb_ind`)
- `sensor.aldes_inspirair_home_sc150_codice_modalita_attiva` (`current_mode`)
- `sensor.aldes_inspirair_home_sc150_versione_firmware_uc` / `versione_firmware_wi_fi` (`Vers_UC` / `Vers_W`)

*(I sensori opzionali per sonde accessorie CO2, PM2.5, VOC e potenze elettriche vengono creati ma lasciati disabilitati di default per mantenere pulita l'interfaccia, e possono essere attivati manualmente da Home Assistant se presenti sull'impianto).*

### Architettura del Codice

Il progetto è suddiviso in moduli Python indipendenti e commentati all'interno di `aldes-bridge/server/`:

- `main.py` — Punto di ingresso dell'add-on e gestione dei segnali di sistema.
- `bridge.py` — Gestione sessione TLS con la Connect Box, loop MQTT verso Home Assistant, verifica comandi e Grace Timer.
- `discovery.py` — Generazione e pulizia dei payload di Auto-Discovery per Home Assistant.
- `filters.py` — Logica di calcolo dell'usura filtri e rilevamento automatico dei reset da display (`FilterTracker`).
- `models.py` — Catalogo strutturato (`SensorDefinition`) dei sensori di telemetria.
- `config.py` — Caricamento variabili d'ambiente, traduzioni JSON e rilevamento automatico del broker Mosquitto.
- `mqtt.py` / `tls.py` — Codec MQTT 3.1.1 leggero e generazione del contesto TLS compatibile con il modulo Wi-Fi `HF-LPB100`.

---

<a name="english"></a>
## English

Native **Home Assistant** add-on providing **100% local control** and full telemetry monitoring for the **Aldes InspirAIR Home SC150** heat recovery ventilation unit (via **Aldes Connect Box**), completely eliminating reliance on Aldes cloud servers.

> **Disclaimer**
> This add-on is an independent, hobbyist open-source project. **The author is in no way affiliated with, associated with, authorized, sponsored by, or officially connected to Aldes** (or any of its subsidiaries or affiliates).
> Use of this software is entirely at your own risk. The author assumes no responsibility or liability for any malfunctions, system lockups, data loss, or damage to the Aldes InspirAIR Home SC150 unit, the Aldes Connect Box module, your electrical/HVAC system, or your Home Assistant installation resulting from the use of this add-on.

### Key Features

- **100% Local Control (Cloud-Free):** Intercepts the MQTT over TLS traffic (port `8883` locally redirected to `18883`) sent by the Connect Box to `aldesiotsuite.azure-devices.net`, handling telemetry and commands directly within your local network.
- **Native MQTT Auto-Discovery:** Automatically detects Home Assistant's Mosquitto broker via the Supervisor API and registers all entities without requiring manual configuration in `configuration.yaml`.
- **Operating Mode Selector (`select`):** Direct control over the supported ventilation modes:
  * **Daily (`V`)**
  * **Kitchen (`Y`)**
  * **Boost (`X`)**
  * **Holidays (`W`)** — featuring automatic generation of the concatenated UTC time window string (`W<start_UTC>Z<end_UTC>Z`).
- **Command Verification & Serial Protection:** Enforces a 2-second safety interval between JSON-RPC packets to avoid flooding the Wi-Fi module's (`HF-LPB100`) UART serial line, coupled with an automatic verification system that resends the command if the unit does not confirm the mode change within 15 seconds.
- **Connection Stability (Grace Timer & Extended Timeout):**
  * **Grace Timer (30s):** Masks the normal ~5-second reconnections performed by the Connect Box every 5 hours during session token renewal, preventing false `Disconnected` states in Home Assistant's history.
  * **660s TLS Timeout:** Matched to the unit's 10-minute telemetry reporting interval to prevent read-timeout disconnections.
- **Smart Filter Monitoring (`FilterTracker`):** Automatically detects when the `ff_cpt` counter is reset from the unit's physical display after filter replacement, persisting the reset timestamp to disk (`/config/aldes/filters.json`) and calculating elapsed days, remaining days, and estimated wear percentage.

### Network Prerequisite (Local DNS)

The Aldes Connect Box connects to the cloud hostname `aldesiotsuite.azure-devices.net` on TCP port `8883`.
To route traffic to Home Assistant without physically modifying the Connect Box, configure a **DNS Rewrite** rule on your local DNS server (e.g., **AdGuard Home**, **Pi-hole**, **UniFi**, **MikroTik**, or a compatible router):

```text
aldesiotsuite.azure-devices.net  --->  <HOME_ASSISTANT_IP_ADDRESS>
```

At startup, the add-on automatically applies an `iptables` (`PREROUTING`) rule that forwards incoming packets on port `8883` to the internal TLS bridge port `18883`.

### Installation on Home Assistant

1. In Home Assistant, navigate to **Settings** → **Add-ons** → **Add-on Store**.
2. Click the **three dots** in the top-right corner and select **Repositories**.
3. Paste the URL of this repository:
   ```text
   [https://github.com/David-PLC/aldes-bridge-sc150](https://github.com/David-PLC/aldes-bridge-sc150)
   ```
4. Click **Add**, then close the dialog.
5. Find **Aldes Bridge SC150** in the add-on list, click **Install**, and enable **Start on boot** and **Watchdog**.

### Configuration

The add-on works out of the box with default settings (auto-detecting Home Assistant's `core-mosquitto` broker). You can customize the following parameters in the add-on's **Configuration** tab:

| Option | Default | Description |
| :--- | :---: | :--- |
| `mqtt_port` | `18883` | Local port where the TLS server listens for the Connect Box (redirects `8883` → `18883`). |
| `box_ip` | `""` | *(Optional)* IP address of the Connect Box to restrict the `iptables` rule exclusively to VMC traffic. |
| `filter_months` | `6` | Nominal filter lifespan in months (`6` months = 180 days) used to calculate remaining days. |
| `language` | `"it"` | Language used for entity names generated in Home Assistant (`translations/<lang>.json`). |
| `ha_mqtt_host` | `""` | *(Optional)* MQTT broker host. Leave empty for automatic discovery via the Supervisor API. |
| `ha_mqtt_port` | `1883` | TCP port of the Home Assistant MQTT broker. |
| `ha_mqtt_user` | `""` | *(Optional)* MQTT username (if not automatically managed by the Supervisor). |
| `ha_mqtt_password` | `""` | *(Optional)* MQTT password (if not automatically managed by the Supervisor). |

### Exposed Entities in Home Assistant

#### Control & Connectivity
- **VMC Mode (`select`)** — Mode selector (`Daily` / `V`, `Kitchen` / `Y`, `Boost` / `X`, `Holidays` / `W`)
- **Connect Box Connectivity (`binary_sensor`)** — TLS connection status of the Aldes Connect Box

#### Filter Monitoring
- **Filter Remaining Days (`sensor`)** — Days remaining before filter replacement
- **Filter Elapsed Days (`sensor`)** — Days elapsed since the last detected filter reset
- **Filter Estimated Wear (`sensor`)** — Calculated wear percentage based on `filter_months`
- **Filter Last Reset (`sensor`)** — Timestamp of the last detected filter change/reset
- **Box Filter Counter (`sensor`)** — Raw `ff_cpt` value reported by the Connect Box
- **Filter Pressure Drop Index (`sensor`)** — Pressure drop indicator (`dep_ind`)

#### Temperatures, Airflow & Fan Speeds
- **Outdoor Air Temperature** (`outside_tpt`, °C)
- **Extract Air Temperature** (`ext_tpt`, °C)
- **Exhaust Air Temperature** (`reject_tpt`, °C)
- **Extract Airflow** (`extf_flw`, m³/h)
- **Supply Airflow** (`ffe_flw`, m³/h)
- **Extract Fan Speed** (`extf_spd`, rpm)
- **Supply Fan Speed** (`vi_spd`, rpm)
- **VMC Speed Level** (`set_spd`)
- **Bypass Status** (`dtb_ind`)
- **Active Mode Code** (`current_mode`)
- **UC / Wi-Fi Firmware Version** (`Vers_UC` / `Vers_W`)

*(Optional sensors for accessory CO2, PM2.5, VOC probes, and electrical power consumption are registered but disabled by default to keep the UI clean; they can be manually enabled in Home Assistant if installed on your system).*

### Code Architecture

The project is organized into clean, documented Python modules inside `aldes-bridge/server/`:

- `main.py` — Add-on entry point and OS signal handling.
- `bridge.py` — TLS session handler for the Connect Box, Home Assistant MQTT loop, command verification, and Grace Timer.
- `discovery.py` — Generation and cleanup of Home Assistant MQTT Auto-Discovery payloads.
- `filters.py` — Filter wear calculation and automatic physical reset detection (`FilterTracker`).
- `models.py` — Structured telemetry sensor catalog (`SensorDefinition`).
- `config.py` — Environment configuration loader, JSON translations, and automatic Mosquitto broker detection.
- `mqtt.py` / `tls.py` — Lightweight MQTT 3.1.1 codec and legacy-compatible TLS context for the `HF-LPB100` Wi-Fi module.

---

## Riconoscimenti / Acknowledgements

Questo progetto nasce ed evolve grazie al lavoro di reverse engineering e condivisione della community open source / This project builds upon the reverse engineering and open-source contributions of the community:

- **[saniho/aldes-bridge](https://github.com/saniho/aldes-bridge)** — Per l'analisi originale del protocollo di comunicazione TLS/MQTT della Aldes Connect Box, la decodifica dei metodi JSON-RPC e l'idea alla base dell'intercettazione locale / *For the original reverse engineering of the Aldes Connect Box TLS/MQTT protocol, JSON-RPC method decoding, and local interception concept.*
- **[Conedo95/aldes_vmc](https://github.com/Conedo95/aldes_vmc)** — Per gli spunti architetturali e la logica di tracciamento automatico del reset filtri (`ff_cpt`) da cui è stato adattato il modulo `filters.py` / *For architectural inspiration and the automatic filter reset tracking logic (`ff_cpt`) adapted in `filters.py`.*

---

## Licenza / License

Questo progetto è distribuito sotto licenza **MIT**. Consulta il file [LICENSE](LICENSE) per il testo integrale dei termini di utilizzo.  
This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for full details.