"""Constants for the MAM Manager integration.

MyAnonamouse (MAM) integration: dashboard, user stats, and daily automations
(donate to vault, buy VIP, buy upload credit). All MAM API paths and
thresholds are defined here.
"""

from datetime import timedelta

# -----------------------------------------------------------------------------
# Integration identity
# -----------------------------------------------------------------------------
DOMAIN = "mam_manager"

# -----------------------------------------------------------------------------
# Config entry: stored in entry.data (from config flow)
# -----------------------------------------------------------------------------
CONF_BASE_URL = "base_url"       # MAM site base URL
CONF_USER_ID = "user_id"         # MAM user ID (used in API params)
CONF_MAM_ID = "mam_id"           # Session cookie value; MAM may refresh it

DEFAULT_BASE_URL = "https://www.myanonamouse.net"

# -----------------------------------------------------------------------------
# Config options: toggles for daily automations (stored in entry.options)
# -----------------------------------------------------------------------------
CONF_AUTO_BUY_CREDIT = "auto_buy_credit"
CONF_AUTO_DONATE_VAULT = "auto_donate_vault"
CONF_AUTO_BUY_VIP = "auto_buy_vip"

DEFAULT_AUTO_BUY_CREDIT = False
DEFAULT_AUTO_DONATE_VAULT = False
DEFAULT_AUTO_BUY_VIP = False

# -----------------------------------------------------------------------------
# MAM API paths (relative to base URL)
# -----------------------------------------------------------------------------
USER_DATA_PATH = "/jsonLoad.php"
USER_DATA_PARAMS = ("pretty", "notif", "clientStats", "snatch_summary")

# Buy upload credit: GET with query params (spendtype=upload, amount=50)
DEFAULT_BUY_CREDIT_PATH = "/json/bonusBuy.php/?spendtype=upload&amount=50"

# Donate to vault: POST to form with Donation, time, submit (application/x-www-form-urlencoded)
DEFAULT_DONATE_VAULT_PATH = "/millionaires/donate.php"
# Donation amount in points; form accepts 100–2000 in steps of 100
DEFAULT_DONATE_POINTS = 2000

# Buy VIP: GET with query params (spendtype=VIP, amount=max)
DEFAULT_BUY_VIP_PATH = "/json/bonusBuy.php/?spendtype=VIP&amount=max"

# -----------------------------------------------------------------------------
# Automation thresholds (MAM rules / safety)
# -----------------------------------------------------------------------------
# Auto buy VIP only for these classes (case-insensitive)
ALLOWED_CLASSNAMES_FOR_AUTO_VIP = ("vip", "power user")
# Minimum seedbonus (bonus points) required to run each action
MIN_SEEDBONUS_FOR_VIP = 5000
MIN_SEEDBONUS_FOR_CREDIT = 25000
# Minimum ratio required to donate to vault (MAM requirement)
MIN_RATIO_FOR_DONATE = 1.05

# -----------------------------------------------------------------------------
# Persistent storage (Store API)
# -----------------------------------------------------------------------------
STORAGE_KEY = "mam_manager_data"
STORAGE_VERSION = 1
# Keys for "last run" dates (YYYY-MM-DD) so we only run each action once per day
STORAGE_LAST_DONATE_DATE = "last_donate_date"
STORAGE_LAST_BUY_CREDIT_DATE = "last_buy_credit_date"
STORAGE_LAST_BUY_VIP_DATE = "last_buy_vip_date"

# -----------------------------------------------------------------------------
# Coordinator / refresh
# -----------------------------------------------------------------------------
# How often to refetch user data from MAM
SCAN_INTERVAL = timedelta(minutes=15)
