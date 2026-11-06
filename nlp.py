import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from tracker import AranyaVihaaraTracker

WEEKDAYS = {
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6
}

def extract_trek(text):
    """
    Extracts trek metadata from freeform text using alias dictionary
    and substring matching.
    """
    text_lower = text.lower()
    
    # Sort aliases by length descending so longer phrases match first
    catalog = AranyaVihaaraTracker.TREKS_CATALOG
    sorted_keys = sorted(catalog.keys(), key=lambda k: len(k), reverse=True)
    
    for key in sorted_keys:
        # Check word boundary or clean substring match
        pattern = rf'\b{re.escape(key)}\b'
        if re.search(pattern, text_lower) or key in text_lower:
            return catalog[key]
            
    return None

def extract_date(text, reference_date=None):
    """
    Extracts date from text supporting:
    - Relative words: 'today', 'tomorrow', 'day after tomorrow'
    - Weekend phrases: 'this weekend', 'next weekend'
    - Weekday phrases: 'next sunday', 'coming saturday', 'this friday'
    - Explicit dates: '22-11-2026', '22/11/2026', 'Nov 22', '22nd November 2026'
    """
    if reference_date is None:
        reference_date = datetime.now()

    text_lower = text.lower()

    # 1. Day after tomorrow
    if "day after tomorrow" in text_lower:
        target = reference_date + timedelta(days=2)
        return target.strftime("%d-%m-%Y"), target

    # 2. Tomorrow
    if "tomorrow" in text_lower:
        target = reference_date + timedelta(days=1)
        return target.strftime("%d-%m-%Y"), target

    # 3. Today
    if re.search(r'\btoday\b', text_lower):
        return reference_date.strftime("%d-%m-%Y"), reference_date

    # 4. Weekends
    if "this weekend" in text_lower or "upcoming weekend" in text_lower:
        days_ahead = (5 - reference_date.weekday()) % 7  # Saturday
        if days_ahead == 0 and reference_date.hour >= 12:
            days_ahead = 7
        target = reference_date + timedelta(days=days_ahead)
        return target.strftime("%d-%m-%Y"), target

    if "next weekend" in text_lower:
        days_ahead = (5 - reference_date.weekday()) % 7 + 7
        target = reference_date + timedelta(days=days_ahead)
        return target.strftime("%d-%m-%Y"), target

    # 5. Named weekdays: "next sunday", "this saturday"
    for day_name, day_num in WEEKDAYS.items():
        pattern = rf'\b(next|this|coming)?\s*{day_name}\b'
        match = re.search(pattern, text_lower)
        if match:
            prefix = match.group(1) or ""
            days_ahead = (day_num - reference_date.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            if "next" in prefix and days_ahead < 7:
                days_ahead += 7
            target = reference_date + timedelta(days=days_ahead)
            return target.strftime("%d-%m-%Y"), target

    # 6. Explicit numeric DD-MM-YYYY or DD/MM/YYYY
    match_num = re.search(r'\b(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2,4}))?\b', text_lower)
    if match_num:
        d = int(match_num.group(1))
        m = int(match_num.group(2))
        y = match_num.group(3)
        year = int(y) if y else reference_date.year
        if year < 100:
            year += 2000
        try:
            target = datetime(year, m, d)
            return target.strftime("%d-%m-%Y"), target
        except ValueError:
            pass

    # 7. Fuzzy date parsing via dateutil
    # Filter out common trek words so dateutil doesn't get confused
    cleaned = re.sub(r'\b(trek|treks|kudremukh|nethravathi|skandagiri|bandaje|slots?|availability|check|book)\b', '', text_lower, flags=re.IGNORECASE)
    try:
        dt = date_parser.parse(cleaned, fuzzy=True, default=reference_date)
        if dt and dt.date() >= reference_date.date():
            return dt.strftime("%d-%m-%Y"), dt
    except Exception:
        pass

    return None, None

def parse_message(text, reference_date=None):
    """
    Parses a user chat message and returns structured semantic intent.
    """
    text_clean = text.strip()
    trek = extract_trek(text_clean)
    date_str, date_obj = extract_date(text_clean, reference_date)

    return {
        "raw_text": text_clean,
        "trek": trek,
        "date_str": date_str,
        "date_obj": date_obj,
        "is_complete": bool(trek and date_str)
    }
