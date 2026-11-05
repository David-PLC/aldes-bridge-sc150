# Changelog

Tutte le modifiche rilevanti a **Aldes Bridge SC150** sono documentate in questo file.

## [2.1.3] - 2026-11-05

### Corretto
- **Modalità Vacanze (`W`)**: corretto il formato del parametro `changeMode` inviato alla Connect Box utilizzando una singola stringa concatenata (`W<inizio_UTC>Z<fine_UTC>Z`) come richiesto dal firmware della VMC.
- **Import `timedelta`**: aggiunto `timedelta` agli import del modulo `datetime` in `server/main.py`.

## [2.1.2] - 2026-11-04

### Corretto
- **Profilo AppArmor (`apparmor.txt`)**: aggiunto il permesso di lettura esplicito sulla directory `/app/` per consentire a Python di risolvere il pacchetto `server`.
- **Script di avvio (`run.sh`)**: impostato esplicitamente `PYTHONPATH=/app` e directory di lavoro `/app` prima dell'esecuzione del bridge.

## [2.1.1] - 2026-11-04

### Corretto
- **Profilo AppArmor (`apparmor.txt`)**: aggiunto il permesso di lettura esplicito sulla directory `/app/` per consentire a Python di risolvere il pacchetto `server`.
- **Script di avvio (`run.sh`)**: impostato esplicitamente `PYTHONPATH=/app` e directory di lavoro `/app` prima dell'esecuzione del bridge.

## [2.1.0] - 2026-11-04

### Aggiunto
- **Entità `select` nativa (`Modalità VMC`)**: sostituisce la precedente entità `fan` con un selettore dedicato alle 4 modalità operative reali della VMC (`Quotidiano`, `Cucina`, `Boost`, `Vacanze`). La modalità `Z` (`Programma aria`) resta gestita a codice.
- **File di traduzione esterna (`translations/it.json`)**: tutti i nomi dei sensori, delle modalità e dei pulsanti sono caricati dinamicamente da file JSON esterno.
- **Traduzione interfaccia di configurazione (`translations/it.yaml`)**: opzioni dell'add-on tradotte in italiano.
- **Profilo di sicurezza `apparmor.txt`**: aggiunto profilo AppArmor dedicato e rimosso il ruolo `hassio_role: manager` per migliorare il Security Rating di Home Assistant (4/8).

### Modificato
- **Unità di misura in UTF-8**: utilizzo di sequenze Unicode (`°C`, `m³/h`, `µg/m³`) immuni da errori di codifica.
- **Disattivazione sensore `RSSI`**: il sensore del segnale Wi-Fi (fisso su `--%%`) è disattivato e rimosso automaticamente da Home Assistant (`active=False`).

## [2.0.1] - 2026-11-04

### Corretto
- Installazione del pacchetto `cryptography` tramite `pip` nel `Dockerfile` per la generazione del certificato TLS self-signed.

## [2.0.0] - 2026-11-04

### Aggiunto
- Riscrittura completa e leggera del bridge MQTT/TLS specifica per **Aldes InspirAIR Home SC150** con Auto-Discovery MQTT per Home Assistant.