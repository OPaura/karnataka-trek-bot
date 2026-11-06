# Aranya Vihaara Karnataka Trek Telegram Chatbot 🏔️🤖

An intelligent Telegram chatbot that semantically understands natural language queries, extracts the trek and date, and fetches live slot availability from the official Karnataka Forest Department portal [Aranya Vihaara](https://aranyavihaara.karnataka.gov.in/).

---

## 🚀 Features

- **Semantic Natural Language Understanding**:
  - *"Is Kudremukh available on Nov 22nd?"*
  - *"Check slots for Skandagiri next Sunday"*
  - *"Any seats in Bandaje waterfall tomorrow?"*
  - *"Netravati on 25/11/2026"*
  - *"Savandurga this weekend"*
- **Automatic Entity Extraction**:
  - Resolves trek aliases (e.g. `Kudremukh`, `Netravathi`, `KP`, `Bandaje Falls`, `Tadiandamol`).
  - Supports relative dates (`tomorrow`, `this weekend`, `next Sunday`) and absolute dates (`22-11-2026`, `Nov 22nd`).
- **Live Slot Scraping**:
  - Bypasses NIC/Gov SSL revocation errors (`--ssl-no-revoke` / `ssl.CERT_NONE`).
  - Retrieves CSRF session tokens and posts directly to `/availability`.
  - Checks if a date is **Blocked** or outside the 30-day booking window.
- **Interactive Telegram UI**:
  - Quick reply keyboard (`/start`, `/treks`, `/help`).
  - Direct "🎟️ Book Now on Aranya Vihaara" and "🔄 Refresh" inline buttons.

---

## 🛠️ Quick Setup (Takes 2 minutes)

### Step 1: Create your Telegram Bot Token
1. Open the **Telegram** app on your phone or desktop.
2. Search for `@BotFather` (verified bot with blue checkmark).
3. Send `/newbot`.
4. Choose a name (e.g., `Karnataka Trek Slot Tracker`) and username (e.g., `karnataka_trek_bot`).
5. Copy the **HTTP API token** provided (looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

### Step 2: Set the Token
Set the environment variable in your terminal:

**PowerShell:**
```powershell
$env:TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

**Command Prompt (cmd):**
```cmd
set TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### Step 3: Run the Bot
```bash
python telegram_bot.py
```
*(If you haven't set the environment variable, the script will prompt you to enter the token directly in the terminal!)*

---

## 💬 Example Chats

```text
User: Is Kudremukh available on Nov 22nd?
Bot:  🔍 Checking Aranya Vihaara for Kudremukha Trek on 22-11-2026...
      🎉 Slots Available!
      🏔️ Trek: Kudremukha Trek
      📍 District: Chikmagalur
      📅 Date: Sunday, 22 November 2026

      Available Time Slots:
      🟢 06:00 A.M TO 11.00A.M
         👉 82/300 seats available

      ⚡ Total Remaining: 82 seats
      [🎟️ Book Now on Aranya Vihaara] [🔄 Re-check]
```

```text
User: Netravati tomorrow
Bot:  🔍 Checking Aranya Vihaara for Nethravathi Trek on 07-11-2026...
      🎉 Slots Available!
      🟢 06:00 AM TO 11:00 AM
         👉 120/300 seats available
```

---

## 🏔️ Supported Treks (21 Trails)

- **Chikmagalur**: Kudremukha Trek, Bandaje Waterfall Trek, Ettina Bhuja, Kurinjal, Gangadikal, Ballalarayana Durga, Merthigudda, Karshigudda.
- **Dakshina Kannada**: Nethravathi Trek.
- **Chikkaballapura**: Skandagiri Trek, Kaiwara Betta.
- **Kodagu**: Kumaraparvatha (Beedahalli), Tadiyandmole, Talacauvery - Nishaanimotte.
- **Ramanagara & Bengaluru**: Savandurga Trekking, Makalidurga, Hulukudi Betta, Bidirukatte.
- **Kalaburagi**: Chandrampalli Nature Trail.
