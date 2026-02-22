"""Constants for the MAM Manager integration."""

from datetime import timedelta

DOMAIN = "mam_manager"

# Config entry keys
CONF_BASE_URL = "base_url"
CONF_USER_ID = "user_id"
CONF_MAM_ID = "mam_id"  # Cookie value for authentication

# MAM base URL (fixed, not user-configurable)
DEFAULT_BASE_URL = "https://www.myanonamouse.net"

# Options: daily automations (URLs are fixed in code)
CONF_AUTO_BUY_CREDIT = "auto_buy_credit"
CONF_AUTO_DONATE_VAULT = "auto_donate_vault"
CONF_AUTO_BUY_VIP = "auto_buy_vip"

# API paths (fixed)
USER_DATA_PATH = "/jsonLoad.php"
USER_DATA_PARAMS = ("pretty", "notif", "clientStats", "snatch_summary")
DEFAULT_BUY_CREDIT_PATH = "/json/bonusBuy.php/?spendtype=upload&amount=50"
# Vault donate page (from mamplus.js VaultLink; may be form-based)
DEFAULT_DONATE_VAULT_PATH = "/millionaires/donate.php"
DEFAULT_BUY_VIP_PATH = "/json/bonusBuy.php/?spendtype=VIP&amount=max"

DEFAULT_AUTO_BUY_CREDIT = False
DEFAULT_AUTO_DONATE_VAULT = False
DEFAULT_AUTO_BUY_VIP = False

# Auto buy VIP only allowed for these classnames (case-insensitive)
ALLOWED_CLASSNAMES_FOR_AUTO_VIP = ("vip", "power user")
# Minimum seedbonus (bonus points) required to run each action
MIN_SEEDBONUS_FOR_VIP = 5000
MIN_SEEDBONUS_FOR_CREDIT = 25000
# MAM requires ratio >= this to donate to vault
MIN_RATIO_FOR_DONATE = 1.05

STORAGE_KEY = "mam_manager_data"
STORAGE_VERSION = 1

# How often to refresh user data from MAM
SCAN_INTERVAL = timedelta(minutes=15)

# Storage keys for "done today" tracking (date in YYYY-MM-DD)
STORAGE_LAST_DONATE_DATE = "last_donate_date"
STORAGE_LAST_BUY_CREDIT_DATE = "last_buy_credit_date"
STORAGE_LAST_BUY_VIP_DATE = "last_buy_vip_date"
