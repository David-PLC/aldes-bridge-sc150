# Changelog

Tutte le modifiche rilevanti a **Aldes Bridge SC150** sono documentate in questo file.

## [2.2.2] - 2026-11-05

### Ottimizzato
- **Timeout TLS del socket**: elevato il timeout di lettura del socket a **660 secondi (11 minuti)** all'interno del gestore di sessione (`server/bridge.py`), eliminando alla radice le disconnessioni periodiche per timeout causate dai ritardi del modulo Wi-Fi HF-LPB100.

## [2.2.1] - 2026-11-05

### Aggiunto
- **Modifiche grafiche**: Aggiunta icona e logo

## [2.2.0] - 2026-11-05

### Aggiunto
- **Monitoraggio intelligente dei filtri (`server/filters.py`)**: rilevamento automatico del reset filtri eseguito dal display della VMC (`ff_cpt`), salvataggio persistente della data di reset in `/config/aldes/filters.json` ed esposizione di 4 nuovi sensori dedicati (`Giorni Residui Filtro`, `Giorni Utilizzo Filtro`, `Usura Stimata Filtro`, `Ultimo Reset Filtro`).
- **Opzione `filter_months`**: nuovo parametro nella configurazione dell'add-on per impostare la durata nominale dei filtri in mesi (default `6` mesi = 180 giorni).
- **Filtro anti-disconnessione (Grace Timer 30s)**: eliminati i falsi stati `Disconnesso` di 5 secondi causati dal rinnovo sessione TLS che la Connect Box esegue ogni 5 ore.

### Modificato
- **Architettura modulare del codice**: suddivisione del vecchio file monolitico in moduli specializzati e commentati (`models.py`, `config.py`, `filters.py`, `discovery.py`, `bridge.py`, `main.py`) con variabili standardizzate in inglese.

## [2.1.3] - 2026-11-05

### Corretto
- **ModalitÃ  Vacanze (`W`)**: parametro `changeMode` formattato come stringa singola concatenata (`W<inizio_UTC>Z<fine_UTC>Z`).
- **Normalizzazione fine riga LF**: garantiti fine riga Unix su `run.sh` e `apparmor.txt`.