import os
import sys
import time
import json
import logging
import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tracker import AranyaVihaaraTracker
from nlp import parse_message, extract_trek, extract_date

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("AranyaTelegramBot")

class AranyaTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.tracker = AranyaVihaaraTracker()
        self.last_update_id = 0
        self.session = requests.Session()
        self.session.verify = False

    def get_updates(self, offset: int = 0, timeout: int = 25):
        try:
            url = f"{self.api_url}/getUpdates"
            params = {"offset": offset, "timeout": timeout}
            resp = self.session.get(url, params=params, timeout=timeout + 10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
            else:
                logger.error(f"Telegram API Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.warning(f"Error fetching updates: {e}")
        return []

    def send_chat_action(self, chat_id: int, action: str = "typing"):
        try:
            self.session.post(
                f"{self.api_url}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
                timeout=5
            )
        except Exception:
            pass

    def send_message(self, chat_id: int, text: str, reply_markup=None, parse_mode: str = "HTML"):
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            resp = self.session.post(f"{self.api_url}/sendMessage", json=payload, timeout=10)
            return resp.json()
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            return None


    def format_availability_response(self, trek_info: dict, date_str: str, result: dict):
        # Format date for display
        try:
            dt = datetime.strptime(date_str, "%d-%m-%Y")
            formatted_date = dt.strftime("%A, %d %B %Y")
        except Exception:
            formatted_date = date_str

        trek_name = trek_info['name']
        district = trek_info['district']

        if result['status'] == "blocked":
            msg = (
                f"🚫 <b>{trek_name} is BLOCKED</b>\n"
                f"📍 District: {district}\n"
                f"📅 Date: {formatted_date}\n\n"
                f"⚠️ The Karnataka Forest Department has marked this date as <b>BLOCKED/CLOSED</b> for trekking."
            )
            return msg, None

        if result['status'] == "too_early":
            msg = (
                f"⚠️ <b>Booking Not Open Yet / Lead Time Rule</b>\n"
                f"🏔️ Trek: <b>{trek_name}</b>\n"
                f"📅 Date: {formatted_date}\n\n"
                f"Treks must be booked at least 1 day in advance (or 2 days after 12:00 PM cutoff)."
            )
            return msg, None

        if result['status'] == "too_far":
            msg = (
                f"⏳ <b>Outside Advance Booking Window</b>\n"
                f"🏔️ Trek: <b>{trek_name}</b>\n"
                f"📅 Date: {formatted_date}\n\n"
                f"Advance bookings are only allowed up to <b>30 days</b>. Please choose a date within the next 30 days."
            )
            return msg, None

        slots = result.get('slots', [])
        total_avail = result.get('total_available', 0)

        if not slots or total_avail == 0:
            msg = (
                f"❌ <b>No Available Slots Found</b>\n\n"
                f"🏔️ Trek: <b>{trek_name}</b>\n"
                f"📍 District: {district}\n"
                f"📅 Date: <b>{formatted_date}</b>\n\n"
                f"All slots for this date appear to be fully booked. Check again later for cancellations or try another date!"
            )
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔄 Refresh", "callback_data": f"check:{trek_info['id']}:{date_str}"}],
                    [{"text": "🌐 Open Aranya Vihaara", "url": "https://aranyavihaara.karnataka.gov.in/"}]
                ]
            }
            return msg, reply_markup

        # Available slots
        slot_lines = []
        for s in slots:
            seats = s['available']
            total = s['total']
            time_range = s['time']
            status_icon = "🟢" if seats > 20 else ("🟡" if seats > 0 else "🔴")
            slot_lines.append(f"{status_icon} <b>{time_range}</b>\n   👉 <b>{seats}/{total}</b> seats available")

        slots_formatted = "\n\n".join(slot_lines)

        msg = (
            f"🎉 <b>Slots Available!</b>\n\n"
            f"🏔️ Trek: <b>{trek_name}</b>\n"
            f"📍 District: {district}\n"
            f"📅 Date: <b>{formatted_date}</b>\n\n"
            f"<b>Available Time Slots:</b>\n"
            f"{slots_formatted}\n\n"
            f"⚡ Total Remaining: <b>{total_avail} seats</b>\n"
            f"🔗 Book directly on the official portal below:"
        )

        reply_markup = {
            "inline_keyboard": [
                [{"text": "🎟️ Book Now on Aranya Vihaara", "url": "https://aranyavihaara.karnataka.gov.in/"}],
                [{"text": "🔄 Re-check", "callback_data": f"check:{trek_info['id']}:{date_str}"}]
            ]
        }
        return msg, reply_markup

    def handle_message(self, message: dict):
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        if not text:
            return

        # 1. /start command
        if text.startswith("/start"):
            welcome = (
                f"🌿 <b>Welcome to Karnataka Trek Slot Tracker Bot!</b> 🏔️\n\n"
                f"I track live slot availability for all Karnataka Forest Department treks directly from "
                f"<a href='https://aranyavihaara.karnataka.gov.in/'>Aranya Vihaara</a>.\n\n"
                f"💬 <b>Just type naturally! For example:</b>\n"
                f"• <i>\"Is Kudremukh available on Nov 22nd?\"</i>\n"
                f"• <i>\"Check slots for Skandagiri next Sunday\"</i>\n"
                f"• <i>\"Any seats in Bandaje waterfall tomorrow?\"</i>\n"
                f"• <i>\"Netravati on 25-11-2026\"</i>\n\n"
                f"Commands:\n"
                f"/treks - List all supported treks\n"
                f"/help - Help & syntax"
            )
            keyboard = {
                "keyboard": [
                    [{"text": "Check Kudremukh (This Weekend)"}, {"text": "Check Skandagiri (Tomorrow)"}],
                    [{"text": "🏔️ All Treks"}, {"text": "❓ Help"}]
                ],
                "resize_keyboard": True
            }
            self.send_message(chat_id, welcome, reply_markup=keyboard)
            return

        # 2. /treks command
        if text.startswith("/treks") or text == "🏔️ All Treks":
            treks_msg = (
                f"🏔️ <b>Supported Karnataka Treks:</b>\n\n"
                f"<b>Chikmagalur:</b>\n"
                f"• Kudremukha Trek\n"
                f"• Bandaje Waterfall Trek\n"
                f"• Ettina Bhuja\n"
                f"• Kurinjal Trek\n"
                f"• Gangadikal Trek\n"
                f"• Ballalarayana Durga\n"
                f"• Merthigudda | Karshigudda\n\n"
                f"<b>Dakshina Kannada:</b>\n"
                f"• Nethravathi Trek\n\n"
                f"<b>Chikkaballapura:</b>\n"
                f"• Skandagiri Trek\n"
                f"• Kaiwara Betta\n\n"
                f"<b>Kodagu:</b>\n"
                f"• Kumaraparvatha (Beedahalli)\n"
                f"• Tadiyandmole Trek\n"
                f"• Talacauvery - Nishaanimotte\n\n"
                f"<b>Ramanagara & Bengaluru:</b>\n"
                f"• Savandurga Trekking\n"
                f"• Makalidurga | Hulukudi Betta\n\n"
                f"👉 <i>Type any trek name with a date to check availability!</i>"
            )
            self.send_message(chat_id, treks_msg)
            return

        # 3. /help command
        if text.startswith("/help") or text == "❓ Help":
            help_msg = (
                f"💡 <b>How to Use This Bot:</b>\n\n"
                f"You can talk to me in plain English! I extract both the <b>trek name</b> and the <b>date</b> automatically.\n\n"
                f"<b>Examples:</b>\n"
                f"1️⃣ <i>\"Is Kudremukh available on Nov 22nd?\"</i>\n"
                f"2️⃣ <i>\"Check Skandagiri slots next Sunday\"</i>\n"
                f"3️⃣ <i>\"Bandaje waterfall tomorrow\"</i>\n"
                f"4️⃣ <i>\"Netravathi on 25/11/2026\"</i>\n\n"
                f"📌 <b>Department Rules:</b>\n"
                f"• Advance bookings allowed up to <b>30 days</b>.\n"
                f"• Minimum 1 day lead time (2 days if booking after 12:00 PM)."
            )
            self.send_message(chat_id, help_msg)
            return

        # 4. Semantic Parsing
        self.send_chat_action(chat_id, "typing")
        parsed = parse_message(text)

        trek = parsed["trek"]
        date_str = parsed["date_str"]

        # Case A: Both Trek & Date understood
        if trek and date_str:
            self.send_message(chat_id, f"🔍 <i>Checking Aranya Vihaara for <b>{trek['name']}</b> on <b>{date_str}</b>...</i>")
            self.send_chat_action(chat_id, "typing")
            
            result = self.tracker.check_availability(trek["district_id"], trek["id"], date_str)
            resp_text, markup = self.format_availability_response(trek, date_str, result)
            self.send_message(chat_id, resp_text, reply_markup=markup)
            return

        # Case B: Trek detected, but date missing
        if trek and not date_str:
            prompt = (
                f"🏔️ I found <b>{trek['name']}</b> ({trek['district']})!\n\n"
                f"📅 <b>Which date would you like to check?</b>\n"
                f"You can say: <i>\"tomorrow\"</i>, <i>\"this Saturday\"</i>, <i>\"next Sunday\"</i>, or <i>\"22-11-2026\"</i>."
            )
            self.send_message(chat_id, prompt)
            return

        # Case C: Date detected, but trek missing
        if date_str and not trek:
            prompt = (
                f"📅 Got the date: <b>{date_str}</b>!\n\n"
                f"🏔️ <b>Which trek are you planning for?</b>\n"
                f"For example: <i>Kudremukha</i>, <i>Netravathi</i>, <i>Skandagiri</i>, <i>Bandaje</i>, or <i>Savandurga</i>."
            )
            self.send_message(chat_id, prompt)
            return

        # Case D: Neither detected
        prompt = (
            f"🤔 I couldn't identify the trek or date from your message.\n\n"
            f"Please mention both the <b>trek name</b> and <b>date</b>, for example:\n"
            f"• <i>\"Check Kudremukh on 22nd Nov\"</i>\n"
            f"• <i>\"Is Netravathi available this Sunday?\"</i>\n"
            f"• <i>\"Bandaje slots for tomorrow\"</i>\n\n"
            f"Or tap /treks to see all supported trails."
        )
        self.send_message(chat_id, prompt)

    def handle_callback_query(self, callback_query: dict):
        chat_id = callback_query["message"]["chat"]["id"]
        data = callback_query.get("data", "")

        if data.startswith("check:"):
            parts = data.split(":")
            if len(parts) == 3:
                trek_id = int(parts[1])
                date_str = parts[2]
                
                # Find trek in catalog
                trek_info = next((t for t in AranyaVihaaraTracker.TREKS_CATALOG.values() if t["id"] == trek_id), None)
                if trek_info:
                    self.send_chat_action(chat_id, "typing")
                    result = self.tracker.check_availability(trek_info["district_id"], trek_info["id"], date_str)
                    resp_text, markup = self.format_availability_response(trek_info, date_str, result)
                    self.send_message(chat_id, resp_text, reply_markup=markup)

    def run(self):
        logger.info("Starting Aranya Vihaara Telegram Bot long polling...")
        print("="*60)
        print("🤖 Aranya Vihaara Telegram Bot is RUNNING!")
        print("Send messages to your bot on Telegram to track trek availability.")
        print("Press Ctrl+C to stop.")
        print("="*60)

        while True:
            try:
                updates = self.get_updates(offset=self.last_update_id + 1, timeout=25)
                for update in updates:
                    self.last_update_id = update["update_id"]
                    if "message" in update:
                        self.handle_message(update["message"])
                    elif "callback_query" in update:
                        self.handle_callback_query(update["callback_query"])
            except KeyboardInterrupt:
                print("\nBot stopped by user.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in polling loop: {e}")
                time.sleep(3)

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Karnataka Trek Bot is running!")

    def log_message(self, format, *args):
        pass  # Suppress health check access logs

DEFAULT_BOT_TOKEN = "9161707501:AAH3q9nvQo84cSnzZ1g4XWJCxQc4lZmjqfY"

def start_health_check_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

if __name__ == "__main__":
    # Start background HTTP health check server for Render free tier
    health_thread = threading.Thread(target=start_health_check_server, daemon=True)
    health_thread.start()

    # Check for BOT_TOKEN in environment, .env file, or fallback
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if (not token or token == "YOUR_BOT_TOKEN_HERE") and os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.strip().split("=", 1)[1].strip()
                    break

    if not token or token == "YOUR_BOT_TOKEN_HERE":
        token = DEFAULT_BOT_TOKEN

    bot = AranyaTelegramBot(token)
    bot.run()

