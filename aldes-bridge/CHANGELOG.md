# Changelog

Tutte le modifiche rilevanti a **Aldes Bridge SC150** sono documentate in questo file.

## [2.1.0] - 2026-11-04

### Aggiunto
- **EntitÃ  `select` nativa (`ModalitÃ  VMC`)**: sostituisce la precedente entitÃ  `fan` con un selettore dedicato alle 4 modalitÃ  operative reali della VMC (`Quotidiano`, `Cucina`, `Boost`, `Vacanze`). La modalitÃ  `Z` (`Programma aria`) resta gestita a codice senza appesantire il selettore.
- **File di traduzione esterna (`translations/it.json`)**: tutti i nomi dei sensori, delle modalitÃ  e dei pulsanti sono ora caricati dinamicamente da file JSON esterno facilmente personalizzabile.
- **Traduzione interfaccia di configurazione (`translations/it.yaml`)**: le opzioni dell'add-on in Home Assistant sono ora descritte in italiano.
- **Profilo di sicurezza `apparmor.txt`**: aggiunto profilo AppArmor dedicato e rimosso il ruolo `hassio_role: manager` superfluo per migliorare il Security Rating di Home Assistant.

### Modificato
- **UnitÃ  di misura garantite in UTF-8**: utilizzo di sequenze Unicode native (`Â°C`, `mÂ³/h`, `Âµg/mÂ³`) immuni da errori di codifica.
- **Disattivazione sensore `RSSI`**: il sensore del segnale Wi-Fi (che restituisce `--%%` fisso sulla box) Ã¨ ora disattivato e rimosso automaticamente da Home Assistant, pur restando predisposto nel codice (`active=False`).

## [2.0.1] - 2026-11-04

### Corretto
- Installazione del pacchetto `cryptography` tramite `pip` per la generazione del certificato TLS self-signed.

## [2.0.0] - 2026-11-04

### Aggiunto
- Riscrittura completa e leggera del bridge MQTT/TLS specifica per **Aldes InspirAIR Home SC150** con Auto-Discovery MQTT per Home Assistant.