# Air Alert Israel (AAI) for Home Assistant

Dieses Update bleibt **kompatibel zur bestehenden Installation**, weil der interne Domain-Ordner weiter
`custom_components/tzevaadom_city` heißt. Du musst die alte Integration also **nicht löschen**.

## Was ist neu?

- Sichtbarer Name: **Air Alert Israel**
- Mehrstadt-Betrieb über **eine** WebSocket-Verbindung
- Robustere Stadtsuche mit **lateinischen Schreibweisen** und Aliasen
- Neuer Diagnose-`binary_sensor` **Verbindung** pro Stadt
- Mitgelieferte **Brand-Assets** (`brand/icon.png`, `brand/logo.png`)

## Update

Den Ordner `custom_components/tzevaadom_city` aus diesem Paket nach:

```text
/config/custom_components/tzevaadom_city
```

kopieren und vorhandene Dateien überschreiben. Danach Home Assistant neu starten.

## Verhalten

Pro Stadt gibt es weiter den Status-Sensor mit:

- `idle`
- `early_warning`
- `alert`
- `all_clear`

Zusätzlich gibt es pro Stadt einen Diagnose-Binary-Sensor für die gemeinsame WebSocket-Verbindung.

Logik:

- `early_warning` bleibt aktiv, bis `all_clear` kommt
- Falls keine Entwarnung ankommt, fällt `early_warning` standardmäßig **frühestens nach 15 Minuten** auf `idle`
- `alert` hat ebenfalls einen Fallback-Timer
- `all_clear` wird kurz angezeigt und fällt dann auf `idle`

## Reconfigure

Über **Neu konfigurieren** können Städte entfernt oder zusätzliche Städte gesucht und hinzugefügt werden.

## Service

- `tzevaadom_city.refresh_city_catalog`
