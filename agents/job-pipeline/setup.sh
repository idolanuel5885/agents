#!/usr/bin/env bash
# ============================================================
#  Job Lead Pipeline — First-time setup
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Job Lead Pipeline — Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Python version check ──────────────────────────────────────────────────────
PYTHON=$(command -v python3.11 2>/dev/null || command -v python3 2>/dev/null || command -v python 2>/dev/null)
if [ -z "$PYTHON" ]; then
  echo "❌  Python 3 not found. Install Python 3.11+ and re-run."
  exit 1
fi
PY_VERSION=$($PYTHON --version 2>&1)
echo "✓  Using: $PY_VERSION"

# ── Install dependencies ──────────────────────────────────────────────────────
# Try a virtual environment first; fall back to --user if venv is unavailable.
if $PYTHON -m venv --help >/dev/null 2>&1; then
  if [ ! -d ".venv" ]; then
    echo "→  Creating virtual environment…"
    $PYTHON -m venv .venv
  fi
  # Activate
  if [ -f ".venv/bin/activate" ]; then
    . .venv/bin/activate
  elif [ -f ".venv/Scripts/activate" ]; then
    . .venv/Scripts/activate
  fi
  PYTHON="python"
  echo "✓  Virtual environment activated"
  echo "→  Installing Python dependencies…"
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
else
  echo "⚠️   python3-venv not available — installing to user site-packages"
  echo "→  Installing Python dependencies…"
  $PYTHON -m pip install --quiet --user --break-system-packages -r requirements.txt 2>/dev/null || \
    $PYTHON -m pip install --quiet --user -r requirements.txt
fi
echo "✓  Python dependencies installed"

# ── Install Playwright browsers ───────────────────────────────────────────────
echo "→  Installing Playwright Chromium browser…"
$PYTHON -m playwright install chromium 2>/dev/null || playwright install chromium
echo "✓  Playwright ready"

# ── .env setup ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠️   Created .env from template."
  echo "    You MUST edit .env before running the pipeline:"
  echo ""
  echo "    Required:"
  echo "      GOOGLE_SHEET_ID          — from your Google Sheet URL"
  echo "      GOOGLE_SERVICE_ACCOUNT_JSON — path to your SA key file"
  echo ""
  echo "    Highly recommended:"
  echo "      PROXYCURL_API_KEY        — for LinkedIn hiring manager lookup (~\$0.01/call)"
  echo "      HUNTER_API_KEY           — for email finding (25 free searches/month)"
  echo ""
  echo "    Optional:"
  echo "      SCRAPER_PROXY            — residential proxy to avoid LinkedIn/Glassdoor blocks"
  echo ""
else
  echo "✓  .env already exists"
fi

# ── Credentials directory ─────────────────────────────────────────────────────
mkdir -p credentials
echo "✓  credentials/ directory ready"

# ── Google Sheets setup instructions ─────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Google Sheets Setup (one-time, 5 minutes)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  1. Go to: console.cloud.google.com"
echo "  2. Create a new project (or use existing)"
echo "  3. Enable APIs:"
echo "     → APIs & Services → Enable APIs → search 'Google Sheets API' → Enable"
echo "     → Also enable 'Google Drive API'"
echo "  4. Create a Service Account:"
echo "     → IAM & Admin → Service Accounts → Create Service Account"
echo "     → Name it anything (e.g. 'job-pipeline')"
echo "  5. Download JSON key:"
echo "     → Click the service account → Keys tab → Add Key → Create new key → JSON"
echo "     → Save to: $PROJECT_DIR/credentials/google_service_account.json"
echo "  6. Create a new Google Sheet at sheets.google.com"
echo "  7. Share the sheet with the service account email (Editor access)"
echo "     → Click Share → paste service account email → Editor"
echo "  8. Copy the Sheet ID into .env:"
echo "     URL looks like: docs.google.com/spreadsheets/d/SHEET_ID/edit"
echo "                                                     ^^^^^^^^^"
echo "     Set: GOOGLE_SHEET_ID=<that value>"
echo ""

# ── Quick verify ──────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Verifying install…"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$PYTHON -c "import httpx, gspread, playwright, rapidfuzz, bs4; print('✓  Core imports OK')" 2>/dev/null || \
  echo "⚠️  Some packages may be missing — try: pip install -r requirements.txt"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your API keys"
echo "    2. Add Google SA JSON to credentials/"
echo "    3. Test (no writes):   python run.py --dry-run"
echo "    4. Full run:           python run.py"
echo ""
echo "  Available scrapers:"
echo "    python run.py --list-scrapers"
echo ""
echo "  Run a single scraper:"
echo "    python run.py --scraper himalayas --dry-run"
echo ""
echo "  Schedule (Mon/Wed/Fri 7am — add to crontab with: crontab -e):"
echo "    0 7 * * 1,3,5 cd $PROJECT_DIR && python run.py >> logs/cron.log 2>&1"
echo ""
