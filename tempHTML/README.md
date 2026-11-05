# Cosmic Mart returns dashboard

Employee view of the review queue. The agent recommends, a person approves.

## Run

```powershell
cd tempHTML
python -m http.server 8000
```

Open http://localhost:8000. Opening `index.html` directly does not work because the page loads JSON with `fetch`.

## Data

- `queue.json` is written by `python pipeline.py` from the repo root (gate, then agent, then queue). It currently holds a real run over the 64 synthetic returns. Field names are the ones the Rule Gate and agent use; see [../docs/CONTRACT.md](../docs/CONTRACT.md) sections 4 and 4b.
- `quarterly_report.json` is separate synthetic sample data for the Reports tab. The pipeline does not produce it.

## What it does

- **To review**: search, filter (destination, Rule Gate result, category, condition), sort, open details, change the destination (only gate-allowed options plus human review), approve.
- **Approved**: view, search, filter, reopen (sends it back to To review).
- **Reports**: KPIs, charts and tables by quarter.
- Returns the Rule Gate stopped (hazard or incomplete data) show the gate's reasons instead of agent figures and can only go to human review.
- Approvals and edits last until the page is reloaded.
