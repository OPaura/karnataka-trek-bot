import urllib.request
import urllib.parse
import http.cookiejar
import ssl
import re
import json
import logging
import os
import socket
from datetime import datetime

logger = logging.getLogger("AranyaTracker")

# Force IPv4 resolution to prevent timeouts on unroutable NAT64 IPv6 (64:ff9b::)
_orig_getaddrinfo = socket.getaddrinfo
def _forced_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host and "aranyavihaara" in host:
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = _forced_ipv4_getaddrinfo


class AranyaVihaaraTracker:
    BASE_URL = "https://aranyavihaara.karnataka.gov.in"

    # Pre-cached catalog of Karnataka Forest Department treks
    # Fetched directly from the live Aranya Vihaara portal
    TREKS_CATALOG = {
        "kudremukha": {"id": 112, "district_id": 17, "name": "Kudremukha Trek", "district": "Chikmagalur"},
        "kudremukh": {"id": 112, "district_id": 17, "name": "Kudremukha Trek", "district": "Chikmagalur"},
        "nethravathi": {"id": 113, "district_id": 24, "name": "Nethravathi Trek", "district": "Dakshina Kannada"},
        "netravati": {"id": 113, "district_id": 24, "name": "Nethravathi Trek", "district": "Dakshina Kannada"},
        "skandagiri": {"id": 80, "district_id": 28, "name": "Skandagiri Trek", "district": "Chikkaballapura"},
        "bandaje": {"id": 84, "district_id": 17, "name": "Bandaje waterfall trek", "district": "Chikmagalur"},
        "bandaje falls": {"id": 84, "district_id": 17, "name": "Bandaje waterfall trek", "district": "Chikmagalur"},
        "kumaraparvatha": {"id": 73, "district_id": 25, "name": "Beedahalli - Kumaraparvatha Trek", "district": "Kodagu"},
        "kumara parvatha": {"id": 73, "district_id": 25, "name": "Beedahalli - Kumaraparvatha Trek", "district": "Kodagu"},
        "kp": {"id": 73, "district_id": 25, "name": "Beedahalli - Kumaraparvatha Trek", "district": "Kodagu"},
        "tadiandamol": {"id": 65, "district_id": 25, "name": "Tadiyandmole Trek", "district": "Kodagu"},
        "tadiyandmole": {"id": 65, "district_id": 25, "name": "Tadiyandmole Trek", "district": "Kodagu"},
        "makalidurga": {"id": 77, "district_id": 21, "name": "Makalidurga", "district": "Bengaluru Rural"},
        "savandurga": {"id": 128, "district_id": 29, "name": "Savandurga Trekking", "district": "Ramanagara"},
        "ettina bhuja": {"id": 98, "district_id": 17, "name": "Ettina Bhuja", "district": "Chikmagalur"},
        "ettinabhuja": {"id": 98, "district_id": 17, "name": "Ettina Bhuja", "district": "Chikmagalur"},
        "kurinjal": {"id": 110, "district_id": 17, "name": "Kurinjal Trek", "district": "Chikmagalur"},
        "gangadikal": {"id": 114, "district_id": 17, "name": "Gangadikal Trek", "district": "Chikmagalur"},
        "merthigudda": {"id": 88, "district_id": 17, "name": "Merthigudda", "district": "Chikmagalur"},
        "ballalarayana durga": {"id": 85, "district_id": 17, "name": "Ballalarayandurgakote", "district": "Chikmagalur"},
        "ballalarayandurgakote": {"id": 85, "district_id": 17, "name": "Ballalarayandurgakote", "district": "Chikmagalur"},
        "karshigudda": {"id": 144, "district_id": 17, "name": "Karshigudda", "district": "Chikmagalur"},
        "hulukudi betta": {"id": 143, "district_id": 21, "name": "HULUKUDI BETTA", "district": "Bengaluru Rural"},
        "kaiwara betta": {"id": 117, "district_id": 28, "name": "Kaiwara Betta", "district": "Chikkaballapura"},
        "bidirukatte": {"id": 131, "district_id": 29, "name": "Bidirukatte Trekking", "district": "Ramanagara"},
        "talacauvery": {"id": 63, "district_id": 25, "name": "Talacauvery - Nishaanimotte Trek", "district": "Kodagu"},
        "nishaanimotte": {"id": 63, "district_id": 25, "name": "Talacauvery - Nishaanimotte Trek", "district": "Kodagu"},
        "chandrampalli": {"id": 126, "district_id": 4, "name": "Chandrampalli Nature Trail", "district": "Kalaburagi"},
    }

    def __init__(self):
        # Ignore SSL revocation and certificate issues common on NIC / state portals
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        handlers = [
            urllib.request.HTTPSHandler(context=self.ctx),
            urllib.request.HTTPCookieProcessor(self.cj)
        ]
        proxy = os.environ.get("INDIAN_PROXY")
        if proxy:
            handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
            logger.info(f"Using proxy: {proxy}")

        self.opener = urllib.request.build_opener(*handlers)

        self.opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'),
            ('Accept-Language', 'en-US,en;q=0.9'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
        ]
        self.csrf_token = None

    def _ensure_session(self):
        """Initializes CSRF token and session cookies if not present."""
        if not self.csrf_token:
            req = urllib.request.Request(self.BASE_URL)
            res = self.opener.open(req, timeout=10)
            html = res.read().decode('utf-8', errors='ignore')
            token_match = re.search(r'name="_token"\s+value="([^"]+)"', html)
            if token_match:
                self.csrf_token = token_match.group(1)
            else:
                raise ValueError("Could not extract CSRF token from Aranya Vihaara portal.")

    def get_blocked_dates(self, district_id, trek_id):
        """Fetches dates that are blocked or closed for booking."""
        self._ensure_session()
        data = urllib.parse.urlencode({
            '_token': self.csrf_token,
            'district_id': district_id,
            'trek_id': trek_id
        }).encode('utf-8')
        req = urllib.request.Request(
            f"{self.BASE_URL}/get-blocked-dates",
            data=data,
            headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': self.BASE_URL}
        )
        res = self.opener.open(req, timeout=10)
        json_resp = json.loads(res.read().decode('utf-8'))
        return json_resp.get('blockedDates', [])


    def check_availability(self, district_id, trek_id, check_in_dd_mm_yyyy):
        """
        Queries slot availability for a given trek and date (DD-MM-YYYY).
        Returns a dict with status, slots list, and metadata.
        """
        self._ensure_session()

        # 1. First check if date is in blocked dates
        try:
            blocked_dates = self.get_blocked_dates(district_id, trek_id)
            if check_in_dd_mm_yyyy in blocked_dates:
                return {
                    "status": "blocked",
                    "date": check_in_dd_mm_yyyy,
                    "message": f"This date ({check_in_dd_mm_yyyy}) is marked as BLOCKED by the Karnataka Forest Department.",
                    "slots": []
                }
        except Exception as e:
            logger.warning(f"Failed to check blocked dates: {e}")

        # 2. Check booking window (1-30 days advance)
        try:
            target_dt = datetime.strptime(check_in_dd_mm_yyyy, "%d-%m-%Y")
            today = datetime.now()
            diff_days = (target_dt.date() - today.date()).days

            if diff_days < 1:
                return {
                    "status": "too_early",
                    "date": check_in_dd_mm_yyyy,
                    "message": "Treks must be booked at least 1 day in advance (or 2 days if booking after 12:00 PM).",
                    "slots": []
                }
            if diff_days > 30:
                return {
                    "status": "too_far",
                    "date": check_in_dd_mm_yyyy,
                    "message": f"Advance bookings are only allowed up to 30 days. {check_in_dd_mm_yyyy} is {diff_days} days away.",
                    "slots": []
                }
        except Exception:
            pass

        # 3. Post to /availability endpoint
        data = urllib.parse.urlencode({
            '_token': self.csrf_token,
            'district': str(district_id),
            'trek': str(trek_id),
            'check_in': check_in_dd_mm_yyyy
        }).encode('utf-8')

        req = urllib.request.Request(
            f"{self.BASE_URL}/availability",
            data=data,
            headers={'Referer': self.BASE_URL}
        )

        try:
            res = self.opener.open(req, timeout=10)
            html = res.read().decode('utf-8', errors='ignore')
        except Exception as e:
            # If session expired, re-init and retry once
            self.csrf_token = None
            self._ensure_session()
            data = urllib.parse.urlencode({
                '_token': self.csrf_token,
                'district': str(district_id),
                'trek': str(trek_id),
                'check_in': check_in_dd_mm_yyyy
            }).encode('utf-8')
            req = urllib.request.Request(f"{self.BASE_URL}/availability", data=data, headers={'Referer': self.BASE_URL})
            res = self.opener.open(req, timeout=10)
            html = res.read().decode('utf-8', errors='ignore')


        # 4. Parse slot cards
        slots = []
        ts_container_match = re.search(r'<div[^>]*class="[^"]*timeslots-container[^"]*"[^>]*>(.*?)</div>\s*</div>\s*<div class="col-sm-4', html, re.DOTALL)
        container_html = ts_container_match.group(1) if ts_container_match else html

        card_blocks = re.findall(r'<div[^>]*class="[^"]*slot_card[^"]*"[^>]*>.*?(?=</div>\s*</div>\s*</div>|$)', container_html, re.DOTALL)

        for block in card_blocks:
            if '${' in block:
                continue  # Skip client-side template literals

            slot_time = re.search(r'class="slot_text[^"]*"[^>]*>([^<]+)</div>', block)
            avail_text = re.search(r'class="available_text[^"]*"[^>]*>([^<]+)</div>', block)

            time_str = slot_time.group(1).replace('&nbsp;', ' ').strip() if slot_time else "Standard Slot"
            avail_str = avail_text.group(1).replace('&nbsp;', ' ').strip() if avail_text else ""

            ratio = re.search(r'(\d+)\s*/\s*(\d+)', avail_str)
            avail_count = int(ratio.group(1)) if ratio else 0
            total_count = int(ratio.group(2)) if ratio else 0

            slots.append({
                'time': time_str,
                'available': avail_count,
                'total': total_count,
                'raw_status': avail_str
            })

        return {
            "status": "success",
            "date": check_in_dd_mm_yyyy,
            "slots": slots,
            "total_available": sum(s['available'] for s in slots)
        }
