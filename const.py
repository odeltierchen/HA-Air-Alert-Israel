"""Constants for the Air Alert Israel integration."""

from __future__ import annotations

DOMAIN = "tzevaadom_city"
INTEGRATION_NAME = "Air Alert Israel"
INTEGRATION_SHORT_NAME = "AAI"

CONF_CITIES = "cities"
CONF_CITY_SEARCH = "city_search"
CONF_KEEP_CITIES = "keep_cities"
CONF_PICKED_CITIES = "picked_cities"
CONF_SEARCH_MORE = "search_more"
CONF_INCLUDE_NATIONWIDE = "include_nationwide"
CONF_EARLY_WARNING_IDLE_AFTER = "early_warning_idle_after"
CONF_ALERT_IDLE_AFTER = "alert_idle_after"
CONF_ALL_CLEAR_IDLE_AFTER = "all_clear_idle_after"

ATTR_CITY_ID = "city_id"
ATTR_CITY_NAME_HE = "city_name_he"

DEFAULT_WS_URL = "wss://ws.tzevaadom.co.il/socket?platform=ANDROID"
CITY_CATALOG_URL = (
    "https://raw.githubusercontent.com/yalihart/homebridge-red-alert/refs/heads/master/cities.json"
)

SERVICE_REFRESH_CITY_CATALOG = "refresh_city_catalog"

DEFAULT_INCLUDE_NATIONWIDE = True
DEFAULT_EARLY_WARNING_IDLE_AFTER = 900
DEFAULT_ALERT_IDLE_AFTER = 900
DEFAULT_ALL_CLEAR_IDLE_AFTER = 90

MIN_EARLY_WARNING_IDLE_AFTER = 900
MIN_ALERT_IDLE_AFTER = 60
MIN_ALL_CLEAR_IDLE_AFTER = 10

STATE_IDLE = "idle"
STATE_EARLY_WARNING = "early_warning"
STATE_ALERT = "alert"
STATE_ALL_CLEAR = "all_clear"

EARLY_WARNING_TITLE_HE = "מבזק פיקוד העורף"
EXIT_TITLE_HE = "עדכון פיקוד העורף"

EARLY_WARNING_KEYWORDS_HE = [
    "בדקות הקרובות",
    "צפויות להתקבל התרעות",
    "ייתכן ויופעלו התרעות",
    "זיהוי שיגורים",
    "שיגורים לעבר ישראל",
    "בעקבות זיהוי שיגורים",
]

EXIT_KEYWORDS_HE = [
    "האירוע הסתיים",
    "הסתיים באזורים",
]

PRIMARY_THREAT_IDS = {0, 2, 5, 7}
NATIONWIDE_CITY_ID = 10000000
NATIONWIDE_CITY_NAME = "רחבי הארץ"

CATALOG_STORE_KEY = f"{DOMAIN}_city_catalog"
CATALOG_STORE_VERSION = 1

PLATFORMS = ["sensor", "binary_sensor"]
