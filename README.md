# Air Alert Israel (AAI) for Home Assistant
(erstellt mit ChatGPT)

**Die Integration dient reinen Informationszwecken! Treffen Sie niemals sicherheitsrelevante Entscheidungen auf Basis der angezeigten Informationen!** 

Integration, die nicht von den IP-Beschränkungen der OREF Alerts abhängig, und so auch für Personen außerhalb von Israel nutzbar ist. Alle Informationen stammen von https://www.tzevaadom.co.il/

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

- `early_warning` bleibt aktiv, bis `alert` oder `all_clear` kommt
- `alert` wartet ebenfalls `all_clear` und ignoriert weitere Meldungen von `early_warning`
- `all_clear` wird kurz angezeigt und fällt dann auf `idle`

## Reconfigure

Über **Neu konfigurieren** können Städte entfernt oder zusätzliche Städte gesucht und hinzugefügt werden.
