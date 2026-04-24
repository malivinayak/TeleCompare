# TeleCompare — India Mobile Plan Finder

A fast, responsive, open-source website that helps users compare Jio, Airtel, Vi, and BSNL prepaid plans and get a personalised recommendation — with no backend server.

**Live demo:** deploy to GitHub Pages (see below).

---

## Features

- **Plan recommendation engine** — score-based algorithm considers budget, data need, validity, 5G, OTT, and operator preference
- **Browse & filter** — filter by operator, validity, price, 5G, OTT; sort by price, cost/day, data/day, cost/GB
- **Side-by-side comparison** — select up to 3 plans and compare in a table; mobile-friendly stacked layout
- **Auto-updating data** — GitHub Actions workflow refreshes `data/plans.json` daily
- **Fully static** — hosts on GitHub Pages with zero backend
- **Mobile-first** — designed for small screens first

---

## Project structure

```
telecompare/
├── index.html                       # Main page
├── style.css                        # All styles (CSS custom properties, no framework)
├── script.js                        # All frontend logic (vanilla JS)
├── data/
│   └── plans.json                   # Plan data (auto-updated by GitHub Actions)
├── scripts/
│   ├── update_plans.py              # Fetches and normalises plan data
│   └── validate_plans.py            # Validates plans.json before commit
├── requirements.txt                 # Python dependencies
├── .github/
│   └── workflows/
│       └── update-plans.yml         # Scheduled data update workflow
└── README.md
```

---

## Quick start (local)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/telecompare.git
cd telecompare

# Serve locally (Python built-in server)
python -m http.server 8080
# Open http://localhost:8080
```

No build step, no Node.js, no bundler required.

---

## Deployment to GitHub Pages

### Option A — GitHub Pages (branch)

1. Push the repo to GitHub.
2. Go to **Settings → Pages**.
3. Set **Source** to `Deploy from a branch`, select `main`, folder `/ (root)`.
4. Save. GitHub Pages will publish the site at `https://YOUR_USERNAME.github.io/REPO_NAME/`.

> **Note:** `data/plans.json` is loaded via `fetch('data/plans.json')`. This works correctly on GitHub Pages because the file is served from the same origin.

### Option B — GitHub Actions deployment (recommended)

Use the official `peaceiris/actions-gh-pages` or GitHub's built-in `actions/deploy-pages` action if you want to deploy from a separate `gh-pages` branch.

---

## Data update pipeline

### How it works

```
[GitHub Actions cron: daily 02:00 UTC]
          │
          ▼
  scripts/update_plans.py
  ├─ Tries live API fetch (if RECHARGE_API_KEY secret is set)
  ├─ Falls back to existing plans.json if fetch fails
  └─ Falls back to built-in seed data if no existing file
          │
          ▼
  scripts/validate_plans.py
  └─ Validates structure, required fields, numeric values, unique IDs
     Exits 1 (fails workflow) if invalid → nothing is committed
          │
          ▼
  git diff data/plans.json
  └─ Only commits if file actually changed
          │
          ▼
  git push → GitHub Pages redeploys automatically
```

### Data status labels

| Status     | Meaning |
|------------|---------|
| `fresh`    | Successfully fetched from a live API |
| `fallback` | Live fetch failed; using previously committed data |
| `manual`   | Using built-in seed data (no live source configured) |

The status and last-updated date are shown in the UI.

### Manual trigger

You can run the workflow manually at any time:

1. Go to your repo on GitHub.
2. Click **Actions → Update Plans Data**.
3. Click **Run workflow**.
4. Optionally tick **Force reset to seed data** to wipe live data and reload from seed.

---

## Adding a live data source (API key)

The frontend **never** sees an API key. Keys stay on the server side (GitHub Actions).

1. Add your secret in GitHub: **Settings → Secrets → Actions → New repository secret**
   - Name: `RECHARGE_API_KEY`
   - Value: your actual key

2. Uncomment the `env:` block in `.github/workflows/update-plans.yml`:
   ```yaml
   env:
     RECHARGE_API_KEY: ${{ secrets.RECHARGE_API_KEY }}
   ```

3. In `scripts/update_plans.py`, implement the `fetch_plan_sources()` function using `os.environ.get("RECHARGE_API_KEY")`. The placeholder comments show exactly where to add this.

The frontend only ever reads `data/plans.json` — never an API key.

---

## Data source strategy (honest assessment)

| Approach | Feasibility | Notes |
|---|---|---|
| Manual JSON updates | ✅ Always works | Requires human effort when prices change |
| Public TRAI tariff data | ⚠️ Limited | TRAI publishes reports but not machine-readable plan APIs |
| Operator website scraping | ⚠️ Fragile | Structures change; may violate ToS; needs maintenance |
| Third-party recharge APIs | ✅ Reliable | Best option; requires paid API key (kept secret via GitHub Secrets) |
| Hybrid (seed + API) | ✅ Recommended | API when available, seed as fallback — exactly what this pipeline does |

**Current default:** seed data (manual). Extend `fetch_plan_sources()` in `update_plans.py` to add a real API.

---

## Recommendation algorithm

Plans are scored on these criteria (higher = better match):

| Criterion | Weight |
|---|---|
| Within budget | 30 pts + bonus for efficient use |
| Validity matches preference | up to 20 pts |
| Data per day matches need | up to 20 pts |
| Low cost per day | up to 15 pts |
| 5G requirement met | ±15 pts |
| OTT requirement met | ±12 pts |
| Preferred operator | 10 pts |
| Good cost per GB | up to 8 pts |
| Unlimited calling | 5 pts |

Plans over budget are disqualified. The top-scoring plan is shown with a plain-English explanation.

---

## Disclaimer

Plan data is provided for reference only. Prices, data allowances, and benefits may vary by telecom circle (state) and change without notice. **Always verify the current plan on the operator's official website before recharging.**

- Jio: [jio.com/recharge](https://www.jio.com/recharge)
- Airtel: [airtel.in/recharge-online](https://www.airtel.in/recharge-online)
- Vi: [myvi.in/prepaid/recharge-plans](https://www.myvi.in/prepaid/recharge-plans)
- BSNL: [selfcare.bsnl.co.in](https://selfcare.bsnl.co.in)

---

## License

MIT — free to use, modify, and deploy.
