# Customer Insights Brief Builder

Turn raw customer-research data — survey responses plus short interview snippets —
into a **one-page, decision-ready insight brief**. Built as a small, fast,
fully-offline Streamlit app that mirrors the real deliverable a customer-research
team ships: a headline finding, the handful of themes that matter (each with a
representative quote and a stat), and a clear list of recommended actions.

> **All data in this project is 100% synthetic.** It is fabricated by
> `data_gen.py` with a fixed random seed and does not describe any real company,
> customer, product, or person. Quotes are invented to demonstrate the analysis
> pipeline only. See the disclaimer below.

## Why this project

This is a portfolio demo for the **Insights Analyst** craft: going from messy
qualitative + quantitative inputs to a crisp, trustworthy brief that someone can
act on in five minutes. It emphasizes **clarity, speed, and storytelling** —
charts follow Cole Nussbaumer Knaflic's *Storytelling with Data* principles
(takeaway titles, one accent color, decluttered axes, direct labels).

## Views

The app has four linked views (sidebar navigation):

1. **Research inputs** — ingest and browse the synthetic survey + interview data
   (quant: NPS 0–10, CSAT 1–5, segment, region; qual: interview snippets).
   Filter and download the raw table.
2. **Themes & sentiment** — top themes/topics by mention count, an overall
   sentiment breakdown, and a sentiment-by-theme view that shows *where the pain
   concentrates*. Sentiment uses a lightweight rule-based lexicon (no API).
3. **Numbers (NPS/CSAT)** — NPS and satisfaction broken out by customer segment,
   with a takeaway-titled chart that points to the lagging segment.
4. **Insight brief** — the auto-assembled one-pager: headline finding, three
   supporting themes (each with a representative synthetic quote and a stat), and
   a recommended-actions list derived from the most negative themes. Exportable
   as plain text.

## How it works

- `data_gen.py` — generates the synthetic dataset. Three correlated personas
  (Promoter / Passive / Detractor) drive both the quant scores and the tone of
  each interview snippet, so the data tells a coherent story (onboarding and
  pricing friction). Fixed seed = reproducible every run.
- `app.py` — pure analysis functions (`sentiment_score`, `theme_frequency`,
  `nps_by_segment`, …) feed four Streamlit views. Themes are detected by keyword
  matching; sentiment is `(#positive − #negative)` lexicon words.

## Run it

```bash
# 1. (optional) create a virtual environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. (optional) generate the CSVs + a sanity summary
python data_gen.py

# 4. launch the app
streamlit run app.py
```

The app generates its data in-memory on launch, so step 3 is optional (it's handy
for inspecting the CSVs or confirming the generator runs).

## Synthetic-data disclaimer

Every number, segment, persona, and quote in this project is **fabricated** by
`data_gen.py` for demonstration purposes. "Northwind Analytics" is a fictional
product. Nothing here reflects real customers, real survey results, or any real
company's performance. No external data source or API is used, and the app runs
entirely offline.

## Author

**Leo Chan** — [github.com/GoldenCrate](https://github.com/GoldenCrate)
