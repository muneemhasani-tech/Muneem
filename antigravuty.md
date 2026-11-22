# BSF Chitin & Chitosan Lead Sourcing — Project State & Progress Log

**Last Updated:** 2026-11-11 22:39 (UTC+06:00)  
**Workspace:** `c:\Users\user\Desktop\Anti Gravity`  
**Objective:** Build a clean, deduplicated B2B supplier and biorefinery lead list for **Black Soldier Fly (BSF / *Hermetia illucens*) chitin, chitosan, insect bioconversion, and biomaterials**.

---

## 1. Accomplishments & Deliverables

| File | Description | Count |
|---|---|---|
| `bsf_leads.csv` | Initial formatted CSV (split `Contact` into `Email` & `Phone / WhatsApp`) | 30 companies |
| `bsf_leads_v2.csv` | Added IndiaMART/TradeKey portal leads + 25 Phase 2 leads | 55 companies |
| `bsf_leads_MASTER.csv` | **Current Master CSV** (all 81 lines verified at 6 columns) | **80 companies** |
| `antigravuty.md` | This status & handoff log | — |

### Master CSV Schema (`bsf_leads_MASTER.csv`)
`Company Name,Core Product/Focus,Website,Email,Phone / WhatsApp,LinkedIn`

### Breakdown of the 80 Companies in `bsf_leads_MASTER.csv`
1. **Consolidated Foundation Batch (59 leads):** Core BSF chitin/chitosan producers (`Entoplast`, `Insectta`, `Chitosan Global`), marine/chemical refiners (`Mediocon Inc.`, `Matsyafed Plant`, `KitoZyme`, `Heppe Medical Chitosan`, `Aura Biopharm`), B2B portal listings (`Holocene Ecosolutions`, `Sandakan Fishmeal Sdn Bhd`, `Youfu Technology Co.`, `Qingdao Sino Crown`, `Bentech`, `Chengdu Baishixing Science`, `Nanjing Hike Biological`), and major BSF producers/tech firms (`InnovaFeed`, `Protix`, `Ynsect`, `Entobel`, `Agronutris`, `Hexafly`, `EnviroFlight`, etc.).
2. **Targeted Web Research Batch (+6 leads):** `InsectBiotech`, `Circa Biotech`, `Grinsect (BSF Systems Kft.)`, `Agroloop`, `INVERS Groupe`, `Flylab (Flylab Tech Co.)`.
3. **IPIFF & NACIA Verified Batch (+15 leads):** `Entoprotech`, `EntoGreen`, `HiProMine`, `LIVIN FARMS`, `REPLOID`, `Chapul Farms`, `Oberland Agriscience`, `Entosystem`, `Grubbly Farms`, `Insect Engineers`, `Kinsect`, `MYIA SA (TicInsect)`, `FlyFeed`, `All Things Bugs`, `3F Waste Recovery` *(marine/by-product chitin)*.

---

## 2. Source Coverage Status

### ✅ Completed / Partially Extracted
- **IPIFF (`https://ipiff.org`)**: Scraped via browser agent; core BSF/bioconversion members verified via web search and merged into `bsf_leads_MASTER.csv`.
- **NACIA (`https://www.nacia.org`)**: Scraped via browser agent; key BSF/biomaterial members verified via web search and merged into `bsf_leads_MASTER.csv`.
- **General Web Search**: Extracted and verified 6 additional BSF/chitosan leads + contact emails/phones/LinkedIn URLs.

### 🔴 Blocked / Pending Manual Browser Access
Automated agents cannot bypass bot checks or log into gated portals:
- **Europages (`https://www.europages.com/`)** — Blocked by AWS WAF human verification challenge.
- **WLW / Wer liefert was (`https://www.wlw.de/en`)** — Blocked by AWS WAF human verification challenge.
- **ThomasNet (`https://www.thomasnet.com/`)** — Blocked by HTTP 403 DataDome protection.

### ⚠️ Incomplete Due to Subagent Quota (`429 RESOURCE_EXHAUSTED`)
The research subagent covering chemical & startup directories stopped early. These still need deeper extraction:
- **Chemical Directories:** GuideChem (`guidechem.com`), LookChem (`lookchem.com`), ChemSrc (`chemsrc.com/en/`) — search by CAS **`9012-76-4`** (Chitosan) and **`1398-61-4`** (Chitin) + `"insect"` / `"Hermetia illucens"`.
- **Business & Startup Directories:** Kompass (`us.kompass.com`), Crunchbase (`crunchbase.com`), Tracxn (`tracxn.com`).
- **B2B Trade Portals (deeper contact reveal):** Alibaba, Made-in-China, IndiaMART, TradeKey, Global Sources, Tridge.
- **Unverified IPIFF/NACIA leftovers (held out until verified):** `Nutri'Earth`, `TecmaFoods`, `Shachar`, `Italian Cricket Farm`, `Gemidan Ecogi`, `Phileo by Lesaffre`, `PreZero`, `Argenta Global`, `NextGen Insect Technologies`, `Beta Catch Inc`, `Centaur Feeds`, `Cowboy Cricket Farms`, `Dalan Animal Health`, `Sure Source Commodities`, `Hermecia`.

---

## 3. Local Environment & Chrome Debugging Setup (Where We Left Off)

### Verified Local Tooling
- **Python:** `3.14.5` (`python -m pip` works; standalone `pip` is not on `PATH`).
- **pip:** `26.1.1`
- **Playwright:** `1.60.0` installed + Chromium (`chromium-1223`) downloaded.
- **Node.js / npm:** `v24.15.0` / `11.12.1`.

### Chrome Remote Debugging State
- Port `9222` returned HTTP 404 (occupied by another local process), so we moved to port **`9223`** with a dedicated `--user-data-dir`.
- **Launch command:**
  ```powershell
  & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="C:\Users\user\chrome-debug"
  ```
- **Technical note for next session:** `playwright.chromium.connect_over_cdp('http://127.0.0.1:9223')` timed out at `180000ms`, whereas Chrome's CDP HTTP endpoint (`http://127.0.0.1:9223/json/list`) responds immediately. Use direct CDP WebSocket (e.g., Node v24 native `WebSocket` to each page's `webSocketDebuggerUrl`) to read DOM/text from unlocked tabs instead of `connect_over_cdp`.
- **Last checked tabs on port `9223`:** Only 3 tabs were open (`chatgpt.com/work/extension/installed`, `Instant Data Scraper - Options`, `chrome://newtab/`). B2B directory tabs had not yet been opened in this `chrome-debug` window.

---

## 4. Exact Next Steps to Resume

1. **Launch (or use) the Chrome debug window on port `9223`:**
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="C:\Users\user\chrome-debug"
   ```
2. **In that window, open & manually unlock the pending directories:**
   - `https://www.europages.com/` (search `"black soldier fly"`, `"insect chitin"`, `"chitosan"`)
   - `https://www.wlw.de/en` (search `"chitosan"`, `"insect chitin"`)
   - `https://www.thomasnet.com/` (search `"chitosan"`)
   - `https://www.guidechem.com/`, `https://www.lookchem.com/`, `https://www.chemsrc.com/en/` (search CAS `9012-76-4` and `1398-61-4`)
   - `https://us.kompass.com/` and `https://www.crunchbase.com/`
3. **Solve any human verification prompts / log in** so supplier listings are visible on screen.
4. **Prompt the agent with `"ready"` or `"check"`** to read all open tabs on `127.0.0.1:9223` via direct CDP WebSocket, extract new suppliers/contacts, deduplicate against the 80 existing companies, and append to `bsf_leads_MASTER.csv`.
5. *(Alternative no-code shortcut)*: On any unlocked Chrome tab, press `Ctrl+A` → `Ctrl+C` and paste the raw text into chat for instant parsing and CSV append.
