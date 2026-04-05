# Air Alert Israel (AAI) for Home Assistant
(erstellt mit ChatGPT)

Integration, die nicht von den IP-Beschränkungen der OREF Alerts abhängig, und so auch für Personen außerhalb von Israel nutzbar ist.

- Sichtbarer Name: **Air Alert Israel**
- Mehrstadt-Betrieb über **eine** WebSocket-Verbindung
- Stadtsuche mit **hebräischen** und **lateinischen** Schreibweisen und Aliasen
- Diagnose-Sensor für die Websocket-Verbindung pro Stadt

## Verhalten

Pro Stadt gibt es einen Status-Sensor mit:

- `idle`
- `early_warning`
- `alert`
- `all_clear`

Zusätzlich gibt es pro Stadt einen Diagnose-Binary-Sensor zur Kontrolle der WebSocket-Verbindung.

Logik:

- `early_warning` bleibt aktiv, bis `all_clear` kommt
- Falls keine Entwarnung ankommt, fällt `early_warning` standardmäßig ** nach 15 Minuten** auf `idle`
- `alert` hat ebenfalls einen Fallback-Timer
- `all_clear` wird kurz angezeigt und fällt dann auf `idle`

## Reconfigure

Über **Neu konfigurieren** können Städte entfernt oder zusätzliche Städte gesucht und hinzugefügt werden.

## Service

- `tzevaadom_city.refresh_city_catalog`
