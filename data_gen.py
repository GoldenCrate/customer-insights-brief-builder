"""
data_gen.py — Synthetic data generator for the Customer Insights Brief Builder.

ALL DATA PRODUCED HERE IS FABRICATED / SYNTHETIC. It does not describe any real
company, customer, product, or person. Quotes are invented to demonstrate the
analysis pipeline only. A fixed random seed makes every run reproducible.

Scenario (invented): "Northwind Analytics" is a fictional B2B SaaS product.
We simulate a post-release customer-research study combining:
  - a quantitative survey (NPS 0-10, CSAT 1-5, by customer segment), and
  - short qualitative interview snippets, each written to evoke common themes.

Run directly to write CSVs and print a quick sanity summary:
    python data_gen.py
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pandas as pd

SEED = 42
N_RESPONSES = 240

SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]
SEGMENT_WEIGHTS = [0.45, 0.35, 0.20]
PLANS = {"SMB": "Starter", "Mid-Market": "Growth", "Enterprise": "Scale"}
REGIONS = ["North America", "EMEA", "APAC"]

# ---------------------------------------------------------------------------
# Theme library. Each theme owns (a) keywords used by the analysis layer to
# detect it in free text and (b) a pool of SYNTHETIC sentence fragments that
# the generator stitches into interview snippets.
# ---------------------------------------------------------------------------
THEMES = {
    "Onboarding": {
        "keywords": ["onboard", "setup", "set up", "getting started", "ramp",
                     "tutorial", "first week", "learning curve"],
        "positive": [
            "onboarding was smooth and we were live in a few days",
            "the setup wizard made getting started painless",
            "our team ramped faster than expected",
        ],
        "negative": [
            "onboarding felt confusing and the setup took weeks",
            "getting started had a steep learning curve with little guidance",
            "the first week of setup was frustrating and under-documented",
        ],
    },
    "Pricing": {
        "keywords": ["price", "pricing", "cost", "expensive", "value",
                     "budget", "billing", "invoice", "renewal cost"],
        "positive": [
            "the pricing feels fair for the value we get",
            "cost is reasonable compared to the alternatives we evaluated",
        ],
        "negative": [
            "pricing is expensive and hard to justify to finance",
            "the cost jumped at renewal and the value was unclear",
            "billing is confusing and the invoices are hard to read",
        ],
    },
    "Support": {
        "keywords": ["support", "help desk", "ticket", "response time",
                     "customer service", "account manager", "rep"],
        "positive": [
            "support is responsive and resolves our tickets quickly",
            "our account manager is proactive and genuinely helpful",
        ],
        "negative": [
            "support is slow and tickets sit for days without a reply",
            "it is hard to reach a human when something breaks",
        ],
    },
    "Performance": {
        "keywords": ["slow", "fast", "speed", "performance", "lag", "latency",
                     "load time", "crash", "timeout", "freeze"],
        "positive": [
            "the dashboards load fast even with large datasets",
            "performance has been snappy and reliable day to day",
        ],
        "negative": [
            "the app is slow and large reports time out",
            "we see lag and occasional crashes during peak hours",
        ],
    },
    "Reliability": {
        "keywords": ["reliable", "reliability", "uptime", "downtime", "outage",
                     "stable", "unstable", "bug", "broken"],
        "positive": [
            "it has been rock solid with no outages this quarter",
            "the platform is stable and we trust the numbers",
        ],
        "negative": [
            "we hit an outage last month that stalled our reporting",
            "random bugs make us double-check the data by hand",
        ],
    },
    "Features": {
        "keywords": ["feature", "integration", "api", "export", "dashboard",
                     "report", "customization", "roadmap", "missing"],
        "positive": [
            "the integrations cover every tool in our stack",
            "custom dashboards let us answer questions in minutes",
        ],
        "negative": [
            "a few key integrations are missing from the roadmap",
            "exporting is clunky and the reports lack customization",
        ],
    },
    "Usability": {
        "keywords": ["ui", "ux", "interface", "intuitive", "confusing",
                     "easy to use", "navigation", "clunky", "clean", "design"],
        "positive": [
            "the interface is clean and intuitive for non-technical staff",
            "navigation is easy and new users find their way fast",
        ],
        "negative": [
            "the interface is cluttered and navigation is confusing",
            "the UX feels clunky and simple tasks take too many clicks",
        ],
    },
}

CONNECTORS = [
    "Honestly,", "For us,", "Day to day,", "If I'm candid,",
    "From the team's view,", "Overall,", "To be fair,",
]

# ---------------------------------------------------------------------------
# Lightweight sentiment lexicon (offline, no API). Used both to COLOR the
# generated snippets and, independently, by the analysis layer in app.py.
# ---------------------------------------------------------------------------
POSITIVE_WORDS = {
    "smooth", "painless", "fast", "faster", "snappy", "reliable", "solid",
    "stable", "responsive", "proactive", "helpful", "fair", "reasonable",
    "clean", "intuitive", "easy", "love", "great", "excellent", "happy",
    "impressed", "trust", "quickly", "recommend", "valuable",
}
NEGATIVE_WORDS = {
    "confusing", "frustrating", "slow", "lag", "crash", "crashes", "outage",
    "bug", "bugs", "broken", "expensive", "clunky", "cluttered", "steep",
    "missing", "unclear", "hard", "stalled", "timeout", "freeze", "unstable",
    "disappointed", "difficult", "painful", "worst",
}


@dataclass
class Persona:
    """Drives correlated quant + qual so the dataset tells a coherent story."""
    label: str
    nps_range: tuple
    csat_range: tuple
    tone: str  # "positive" | "negative" | "mixed"


PERSONAS = [
    Persona("Promoter", (9, 10), (4, 5), "positive"),
    Persona("Passive", (7, 8), (3, 4), "mixed"),
    Persona("Detractor", (0, 6), (1, 3), "negative"),
]
# Deliberately skewed so there is a real story to find (onboarding/pricing pain).
PERSONA_WEIGHTS = [0.38, 0.30, 0.32]


def _pick(rng: random.Random, seq):
    return seq[rng.randrange(len(seq))]


def _weighted(rng: random.Random, options, weights):
    return rng.choices(options, weights=weights, k=1)[0]


def _build_snippet(rng: random.Random, persona: Persona):
    """Return (snippet_text, list_of_theme_labels)."""
    theme_names = list(THEMES.keys())
    n_themes = rng.choice([1, 1, 2, 2, 3])
    chosen = rng.sample(theme_names, n_themes)

    clauses = []
    for theme in chosen:
        if persona.tone == "positive":
            pool = THEMES[theme]["positive"]
        elif persona.tone == "negative":
            pool = THEMES[theme]["negative"]
        else:  # mixed personas lean slightly negative on the pain themes
            lean = "negative" if theme in ("Onboarding", "Pricing") else "positive"
            pool = THEMES[theme][lean]
        clauses.append(_pick(rng, pool))

    connector = _pick(rng, CONNECTORS)
    body = "; ".join(clauses)
    snippet = f"{connector} {body}."
    snippet = snippet[0].upper() + snippet[1:]
    return snippet, chosen


def generate_dataset(seed: int = SEED, n: int = N_RESPONSES) -> pd.DataFrame:
    """Build the combined survey + interview-snippet dataset (reproducible)."""
    rng = random.Random(seed)
    rows = []
    start_period = "2026-Q1"

    for i in range(n):
        persona = _weighted(rng, PERSONAS, PERSONA_WEIGHTS)
        segment = _weighted(rng, SEGMENTS, SEGMENT_WEIGHTS)
        region = _pick(rng, REGIONS)

        nps = rng.randint(*persona.nps_range)
        csat = rng.randint(*persona.csat_range)

        snippet, themes = _build_snippet(rng, persona)

        rows.append(
            {
                "respondent_id": f"R{i + 1:04d}",
                "period": start_period,
                "segment": segment,
                "plan": PLANS[segment],
                "region": region,
                "nps_score": nps,
                "csat_1_5": csat,
                "persona": persona.label,
                "interview_snippet": snippet,
                "themes": "|".join(themes),
            }
        )

    df = pd.DataFrame(rows)
    return df


def nps_category(score: int) -> str:
    if score >= 9:
        return "Promoter"
    if score >= 7:
        return "Passive"
    return "Detractor"


def main() -> None:
    df = generate_dataset()
    df.to_csv("survey_responses.csv", index=False)

    # A thin "interviews-only" view for anyone who wants just the qual.
    interviews = df[["respondent_id", "segment", "persona",
                     "interview_snippet", "themes"]].copy()
    interviews.to_csv("interview_snippets.csv", index=False)

    print("=== Synthetic dataset written ===")
    print(f"Rows: {len(df)}")
    print(f"Files: survey_responses.csv, interview_snippets.csv")
    print("\nSegment counts:")
    print(df["segment"].value_counts().to_string())
    print("\nNPS category counts:")
    print(df["nps_score"].apply(nps_category).value_counts().to_string())
    print(f"\nMean CSAT: {df['csat_1_5'].mean():.2f}  |  Mean NPS score: {df['nps_score'].mean():.2f}")
    print("\nSample snippet:")
    print(" ", df.iloc[0]["interview_snippet"])


if __name__ == "__main__":
    main()
