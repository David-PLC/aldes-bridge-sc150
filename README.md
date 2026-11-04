# Aldes Bridge SC150 — Home Assistant Add-on

Add-on nativo per **Home Assistant OS** che consente il controllo e il monitoraggio **100% locale** (senza alcuna dipendenza dal cloud Aldes o Microsoft Azure) della VMC a doppio flusso **Aldes InspirAIR Home SC150** equipaggiata con modulo **Aldes Connect Box**.

---

##Indice
1. [Architettura e Funzionamento](#1-architettura-e-funzionamento)
2. [Prerequisiti di Rete (DNS e MQTT)](#2-prerequisiti-di-rete-dns-e-mqtt)
3. [Installazione su Home Assistant](#3-installazione-su-home-assistant)
4. [Configurazione dell'Add-on](#4-configurazione-delladd-on)
5. [Entità Esposte in Home Assistant](#5-entità-esposte-in-home-assistant)
6. [Personalizzazione Nomi e Traduzioni](#6-personalizzazione-nomi-e-traduzioni)
7. [Sicurezza e Permessi (Security Rating)](#7-sicurezza-e-permessi-security-rating)
8. [Risoluzione dei Problemi (Troubleshooting)](#8-risoluzione-dei-problemi-troubleshooting)

---

## 1. Architettura e Funzionamento

La **Aldes Connect Box** comunica nativamente con l'infrastruttura cloud Azure IoT Hub (`aldesiotsuite.azure-devices.net`) tramite una connessione **MQTT over TLS** sulla porta TCP **8883**.

```text
[VMC InspirAIR SC150] <---> [Aldes Connect Box]
                                    |
                     (DNS locale: aldesiotsuite.azure-devices.net)
                                    |
                             Porta TCP 8883 (TLS)
                                    v
                       [Add-on Aldes Bridge SC150]
                        (iptables 8883 -> 18883)
                                    |
                           Porta TCP 1883 (MQTT)
                                    v
                     [Mosquitto Broker -> Home Assistant]
```

L'Add-on svolge in automatico le seguenti operazioni:
* **Emulazione Endpoint TLS Azure**: genera all'avvio un certificato X.509 self-signed per il Common Name `aldesiotsuite.azure-devices.net` abilitando il supporto ai cipher suite legacy richiesti dal firmware della Connect Box (`TLSv1` / `SECLEVEL=0`).
* **Intercettazione Porta 8883**: tramite una regola `iptables` (`PREROUTING`), redirige il traffico TCP in ingresso sulla porta `8883` verso la porta interna `18883` del bridge, evitando conflitti con altri servizi dell'host.
* **Auto-Discovery MQTT per Home Assistant**: si autentica automaticamente sul broker Mosquitto tramite l'API del Supervisor di Home Assistant e registra tutte le entità della VMC sotto un unico dispositivo (**Aldes InspirAIR Home SC150**).
* **Controllo Bidirezionale JSON-RPC**: invia i comandi di cambio modalità (`changeMode`) sul topic `devices/<PRODUCT_ID>/messages/devicebound` con conferma immediata dello stato.
* **Cache Persistente**: salva l'ultima telemetria ricevuta in `/config/aldes/telemetry.json`, ripristinando istantaneamente i valori dei sensori anche in caso di riavvio dell'add-on o di Home Assistant.

---

## 2. Prerequisiti di Rete (DNS e MQTT)

Prima di avviare l'Add-on, assicurati di avere:

1. **Mosquitto Broker attivo su Home Assistant**:
   * Installato come Add-on ufficiale (*Impostazioni -> Componenti aggiuntivi -> Mosquitto broker*) e integrato in *Impostazioni -> Dispositivi e servizi -> MQTT*.

2. **Reindirizzamento DNS locale per `aldesiotsuite.azure-devices.net`**:
   * Il server DNS della tua rete locale (**Pi-hole**, **AdGuard Home**, **Unbound**, **Dnsmasq** o router) deve risolvere il dominio cloud Aldes con l'**indirizzo IP locale di Home Assistant**:
     ```text
     aldesiotsuite.azure-devices.net  --->  <IP_HOME_ASSISTANT>
     ```
   * **Nota per utenti Pi-hole / Fritz!Box**:
     * Inserisci il dominio in **Pi-hole -> Local DNS -> DNS Records** associandolo all'IP di Home Assistant.
     * Assicurati che la Aldes Connect Box utilizzi esclusivamente Pi-hole come server DNS (evitando DNS secondari pubblici come `8.8.8.8`).
     * Dopo aver creato la regola in Pi-hole, svuota la cache DNS (`pihole restartdns`) e riavvia elettricamente la Connect Box per forzare una nuova query DNS e l'apertura del socket TLS verso Home Assistant.

---

## 3. Installazione su Home Assistant

1. Apri Home Assistant e vai in **Impostazioni** -> **Componenti aggiuntivi**.
2. Clicca sul pulsante **Raccolta di componenti aggiuntivi** (in basso a destra).
3. Clicca sull'icona con i **tre puntini** in alto a destra e seleziona **Repository**.
4. Incolla l'URL di questa repository GitHub e clicca su **Aggiungi**:
   ```text
   https://github.com/David-PLC/aldes-bridge-sc150
   ```
5. Chiudi la finestra dei repository, ricarica la pagina dello Store e individua **Aldes Bridge SC150**.
6. Clicca su **Installa**, configura eventuali opzioni nella scheda **Configurazione** e premi **Avvia**.

---

## 4. Configurazione dell'Add-on

Nella scheda **Configurazione** dell'Add-on sono disponibili i seguenti parametri:

| Parametro | Valore predefinito | Descrizione |
| :--- | :--- | :--- |
| `mqtt_port` | `18883` | Porta TCP interna su cui ascolta il server TLS del bridge. Lo script di avvio redirige automaticamente la porta `8883` verso questo valore tramite `iptables`. |
| `box_ip` | `""` *(vuoto)* | **Consigliato**: inserisci l'indirizzo IP statico della tua Aldes Connect Box (es. `192.168.179.73`). In questo modo la regola `iptables` intercetterà solo i pacchetti provenienti dalla VMC. Se lasciato vuoto, accetta connessioni sulla porta 8883 da qualsiasi IP della LAN. |
| `language` | `"it"` | Codice lingua utilizzato per caricare le etichette dei sensori e delle modalità dal file `translations/<language>.json`. |
| `ha_mqtt_host` | `""` *(vuoto)* | Host del broker MQTT. Lascia vuoto per usare il rilevamento automatico tramite Home Assistant Supervisor (`core-mosquitto`). |
| `ha_mqtt_port` | `1883` | Porta TCP del broker MQTT di Home Assistant. |
| `ha_mqtt_user` | `""` *(vuoto)* | Utente MQTT. Lascia vuoto per usare le credenziali fornite automaticamente dal Supervisor, oppure specifica un utente Mosquitto dedicato. |
| `ha_mqtt_password` | `""` *(vuoto)* | Password MQTT. Lascia vuoto per usare le credenziali del Supervisor. |

---

## 5. Entità Esposte in Home Assistant

Tutte le entità vengono raggruppate automaticamente sotto il dispositivo **Aldes InspirAIR Home SC150** nell'integrazione MQTT:

### Controlli Operativi
* **Selettore Modalità (`select`) — *Modalità VMC***:
  * **Quotidiano** (Codice `V`): funzionamento standard a portata nominale.
  * **Cucina** (Codice `Y`): portata maggiorata temporizzata per estrazione intensiva cucina.
  * **Boost** (Codice `X`): portata massima temporizzata.
  * **Vacanze** (Codice `W`): portata minima per assenza prolungata (imposta automaticamente l'intervallo date UTC richiesto dal protocollo Aldes).
  * *(La modalità `Z` - Programma aria è gestita internamente a codice per evitare errori di stato se attivata da remoto, ma non è esposta nel menu a tendina).*
* **Pulsanti Rapidi (`button`)**:
  * **Modalità Quotidiano (V)**
  * **Modalità Cucina (Y)**
  * **Modalità Boost (X)**
  * **Modalità Vacanze (W)**

### Sensori Attivi di Default
| Chiave Payload | Nome Entità predefinito (`it.json`) | Unità | Descrizione |
| :--- | :--- | :--- | :--- |
| `outside_tpt` | Temperatura Aria Esterna | `°C` | Temperatura dell'aria esterna aspirata dalla VMC. |
| `ext_tpt` | Temperatura Aria Estratta | `°C` | Temperatura dell'aria interna prelevata dagli ambienti. |
| `reject_tpt` | Temperatura Aria Espulsa | `°C` | Temperatura dell'aria espulsa all'esterno dopo lo scambiatore. |
| `extf_flw` | Portata Estrazione | `m³/h` | Portata volumetrica istantanea sul ramo di estrazione. |
| `ffe_flw` | Portata Insufflazione | `m³/h` | Portata volumetrica istantanea sul ramo di immissione. |
| `extf_spd` | Velocità Ventola Estrazione | `rpm` | Giri al minuto del ventilatore di estrazione. |
| `vi_spd` | Velocità Ventola Insufflazione | `rpm` | Giri al minuto del ventilatore di immissione. |
| `set_spd` | Livello Velocità VMC | `1–3` | Gradino di velocità attivo. |
| `current_mode` | Codice Modalità Attiva | Testo | Lettera grezza della modalità corrente (`V`, `Y`, `X`, `W`, `Z`). |
| `ff_cpt` | Contatore Usura Filtro | `d` | Contatore stato/giorni filtro. |
| `dep_ind` | Indice Depressione Filtri | Intero | Indice di perdita di carico / intasamento filtri. |
| `dtb_ind` | Stato Bypass | Intero | Stato apertura serranda di bypass (`0` = chiuso). |
| `Vers_UC` | Versione Firmware UC | Intero | Versione firmware scheda elettronica Unità Centrale. |
| `Vers_W` | Versione Firmware Wi-Fi | Testo | Versione firmware modulo Aldes Connect Box. |
| — | Connessione Connect Box | `on`/`off` | `binary_sensor` che indica se la Connect Box è connessa in TLS al bridge. |

### Sensori Disabilitati di Default
Sulla **InspirAIR Home SC150** senza accessori opzionali (es. sensore ambientale Aldes Walter o modulo di misura consumi), queste chiavi restituiscono `0` fisso. Vengono create come **disabilitate di default** per mantenere pulita l'interfaccia (attivabili in qualsiasi momento da Home Assistant):
* `Co2_vmc` (CO2 VMC, `ppm`)
* `Pm25_Vmc` (PM2.5 VMC, `µg/m³`)
* `Voc_Vmc` (VOC VMC, `ppm`)
* `cve_csn` (Consumo Ventola Estrazione, `W`)
* `vi_csn` (Consumo Ventola Insufflazione, `W`)
* `tte_csn` (Consumo Totale VMC, `W`)
* `echange_pwr` (Potenza Scambiatore, `W`)

*(Il sensore `RSSI`, che sulla Connect Box restituisce la stringa fissa `--%%`, è mantenuto nel codice sorgente con flag `active=False` e rimosso automaticamente da Home Assistant).*

---

## 6. Personalizzazione Nomi e Traduzioni

Tutti i nomi visualizzati in Home Assistant sono separati dal codice Python e risiedono nel file **`aldes-bridge/translations/it.json`**.

Se desideri rinominare un sensore o creare una nuova traduzione (es. `en.json` o `fr.json`):
1. Modifica le etichette nel file `aldes-bridge/translations/it.json` (oppure crea un nuovo file `<codice_lingua>.json` con la stessa struttura).
2. Incrementa il numero di `version` in `aldes-bridge/config.yaml` ed esegui il push su GitHub.
3. Aggiorna l'Add-on da Home Assistant.

---

## 7. Sicurezza e Permessi (Security Rating)

L'Add-on include un profilo **AppArmor** dedicato (`aldes-bridge/apparmor.txt`) e richiede esclusivamente i privilegi strettamente indispensabili:
* `host_network: true` e `privileged: [NET_ADMIN]`: necessari per applicare la regola `iptables` che intercetta la porta `8883` senza alterare la configurazione di rete della Connect Box.
* `hassio_api: true` e `services: ["mqtt:want"]`: utilizzati con ruolo standard per ottenere in modo sicuro l'indirizzo e le credenziali del broker Mosquitto locale.

---

## 8. Risoluzione dei Problemi (Troubleshooting)

* **La Connect Box non si connette (`Connessione Connect Box: Disconnesso`)**:
  1. Controlla nei log di Pi-hole / DNS locale che la Connect Box stia effettivamente risolvendo `aldesiotsuite.azure-devices.net` con l'IP locale di Home Assistant.
  2. Verifica che il parametro `box_ip` nelle opzioni dell'Add-on corrisponda all'IP reale della Connect Box (oppure lascialo vuoto per accettare connessioni da tutta la sottorete).
  3. Scollega e ricollega l'alimentazione della Connect Box per forzare una riconnessione immediata (la box effettua tentativi con backoff progressivo quando perde il cloud).
* **Errore `CONNACK rifiutato da Mosquitto (rc=4 o rc=5)` nei log**:
  * Inserisci manualmente un nome utente e una password validi di Home Assistant / Mosquitto nei campi `ha_mqtt_user` e `ha_mqtt_password` della scheda Configurazione dell'Add-on e riavvialo.