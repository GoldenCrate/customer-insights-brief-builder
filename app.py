"""
Customer Insights Brief Builder — Streamlit app
-----------------------------------------------
A small, offline portfolio demo that mirrors a customer-research workflow:
ingest survey + interview data, surface the themes and sentiment, quantify
the signal by segment, and auto-assemble a one-page, decision-ready brief.

ALL DATA IS SYNTHETIC (see data_gen.py). Nothing here describes a real
company, customer, or person.

Run:
    pip install -r requirements.txt
    streamlit run app.py

Author: Leo Chan — github.com/GoldenCrate
"""

from __future__ import annotations

import re
from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

from data_gen import (
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    THEMES,
    generate_dataset,
    nps_category,
)

# ---------------------------------------------------------------------------
# Page + light theming
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Customer Insights Brief Builder",
    page_icon="📝",
    layout="wide",
)

# Storytelling-with-Data palette: one accent, grays for context.
ACCENT = "#1f6feb"
ACCENT_SOFT = "#9ec1f5"
POS_COLOR = "#2e7d32"
NEG_COLOR = "#c62828"
NEU_COLOR = "#9e9e9e"
GRAY = "#8a8f98"

_WORD_RE = re.compile(r"[a-z']+")


# ---------------------------------------------------------------------------
# Analysis layer (pure functions, independently testable)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    df = generate_dataset()
    df["nps_category"] = df["nps_score"].apply(nps_category)
    df["sentiment_score"] = df["interview_snippet"].apply(sentiment_score)
    df["sentiment"] = df["sentiment_score"].apply(sentiment_label)
    return df


def sentiment_score(text: str) -> int:
    """Rule-based lexicon score: (#positive words) - (#negative words)."""
    tokens = _WORD_RE.findall(str(text).lower())
    pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    return pos - neg


def sentiment_label(score: int) -> str:
    if score > 0:
        return "Positive"
    if score < 0:
        return "Negative"
    return "Neutral"


def theme_frequency(df: pd.DataFrame) -> pd.DataFrame:
    """Count how many responses mention each theme (keyword detection)."""
    counts: Counter = Counter()
    for snippet in df["interview_snippet"]:
        low = str(snippet).lower()
        for theme, cfg in THEMES.items():
            if any(kw in low for kw in cfg["keywords"]):
                counts[theme] += 1
    out = (
        pd.DataFrame({"theme": list(counts.keys()), "mentions": list(counts.values())})
        .sort_values("mentions", ascending=False)
        .reset_index(drop=True)
    )
    out["share"] = out["mentions"] / len(df)
    return out


def theme_sentiment(df: pd.DataFrame, theme: str) -> dict:
    """Sentiment split + a representative quote for one theme."""
    kws = THEMES[theme]["keywords"]
    mask = df["interview_snippet"].str.lower().apply(
        lambda s: any(kw in s for kw in kws)
    )
    sub = df[mask]
    if sub.empty:
        return {"n": 0, "pos": 0, "neg": 0, "neu": 0, "net": 0.0, "quote": "", "quote_seg": ""}

    pos = int((sub["sentiment"] == "Positive").sum())
    neg = int((sub["sentiment"] == "Negative").sum())
    neu = int((sub["sentiment"] == "Neutral").sum())
    net = (pos - neg) / len(sub)

    # Representative quote: a snippet focused on THIS theme (fewest competing
    # themes) and in the dominant sentiment direction, so the quote reads as
    # being about the theme rather than borrowing another topic's words.
    direction = "Negative" if neg >= pos else "Positive"
    pool = sub[sub["sentiment"] == direction]
    if pool.empty:
        pool = sub
    pool = pool.assign(_n_themes=pool["themes"].str.count(r"\|"))
    fewest = pool["_n_themes"].min()
    focused = pool[pool["_n_themes"] == fewest]
    pick = focused.loc[focused["sentiment_score"].abs().idxmax()]
    return {
        "n": len(sub),
        "pos": pos,
        "neg": neg,
        "neu": neu,
        "net": net,
        "direction": direction,
        "quote": pick["interview_snippet"],
        "quote_seg": pick["segment"],
    }


def nps_by_segment(df: pd.DataFrame) -> pd.DataFrame:
    """Net Promoter Score per segment = %Promoters - %Detractors."""
    rows = []
    for seg, grp in df.groupby("segment"):
        promoters = (grp["nps_category"] == "Promoter").mean()
        detractors = (grp["nps_category"] == "Detractor").mean()
        rows.append(
            {
                "segment": seg,
                "nps": round((promoters - detractors) * 100),
                "n": len(grp),
                "csat": round(grp["csat_1_5"].mean(), 2),
            }
        )
    order = {"SMB": 0, "Mid-Market": 1, "Enterprise": 2}
    return pd.DataFrame(rows).sort_values("segment", key=lambda s: s.map(order)).reset_index(drop=True)


def overall_nps(df: pd.DataFrame) -> int:
    promoters = (df["nps_category"] == "Promoter").mean()
    detractors = (df["nps_category"] == "Detractor").mean()
    return round((promoters - detractors) * 100)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
def view_data(df: pd.DataFrame):
    st.header("1 · Research inputs")
    st.caption(
        "A synthetic study for the fictional product **Northwind Analytics**: "
        "a quantitative survey (NPS, CSAT) joined to short qualitative "
        "interview snippets. One row = one respondent."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Respondents", len(df))
    c2.metric("Segments", df["segment"].nunique())
    c3.metric("Mean CSAT (1–5)", f"{df['csat_1_5'].mean():.2f}")
    c4.metric("Mean NPS score (0–10)", f"{df['nps_score'].mean():.1f}")

    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Respondents by segment")
        seg = df["segment"].value_counts().reset_index()
        seg.columns = ["segment", "count"]
        chart = (
            alt.Chart(seg)
            .mark_bar(color=ACCENT)
            .encode(
                x=alt.X("count:Q", title=None),
                y=alt.Y("segment:N", sort="-x", title=None),
                tooltip=["segment", "count"],
            )
            .properties(height=180)
        )
        st.altair_chart(chart, use_container_width=True)
    with right:
        st.subheader("Response personas")
        per = df["persona"].value_counts().reset_index()
        per.columns = ["persona", "count"]
        st.dataframe(per, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Browse the raw data")
    seg_filter = st.multiselect(
        "Filter by segment", options=sorted(df["segment"].unique()),
        default=sorted(df["segment"].unique()),
    )
    shown = df[df["segment"].isin(seg_filter)]
    st.dataframe(
        shown[
            ["respondent_id", "segment", "plan", "region", "nps_score",
             "csat_1_5", "sentiment", "interview_snippet"]
        ],
        hide_index=True,
        use_container_width=True,
        height=360,
    )
    st.download_button(
        "Download displayed data (CSV)",
        shown.to_csv(index=False).encode("utf-8"),
        file_name="survey_responses_filtered.csv",
        mime="text/csv",
    )


def view_themes(df: pd.DataFrame):
    st.header("2 · Themes & sentiment")
    st.caption(
        "What are people talking about, and how do they feel about it? "
        "Themes are detected by keyword matching; sentiment is a rule-based "
        "lexicon score (no external API)."
    )

    freq = theme_frequency(df)
    top_theme = freq.iloc[0]
    st.markdown(
        f"#### **{top_theme['theme']}** is the most-discussed theme "
        f"— raised by **{top_theme['mentions']} of {len(df)}** respondents "
        f"({top_theme['share']:.0%})"
    )

    freq_disp = freq.copy()
    freq_disp["label"] = (freq_disp["mentions"].astype(str)
                          + " (" + (freq_disp["share"] * 100).round().astype(int).astype(str) + "%)")
    bars = (
        alt.Chart(freq_disp)
        .mark_bar()
        .encode(
            x=alt.X("mentions:Q", title="Respondents mentioning theme"),
            y=alt.Y("theme:N", sort="-x", title=None),
            color=alt.condition(
                alt.datum.theme == top_theme["theme"],
                alt.value(ACCENT),
                alt.value(ACCENT_SOFT),
            ),
            tooltip=["theme", "mentions", alt.Tooltip("share:Q", format=".0%")],
        )
        .properties(height=320)
    )
    labels = bars.mark_text(align="left", dx=4, color=GRAY).encode(text="label:N")
    st.altair_chart(bars + labels, use_container_width=True)

    st.divider()
    st.subheader("Overall sentiment breakdown")
    s1, s2 = st.columns([1, 1])
    sent = df["sentiment"].value_counts().reindex(
        ["Positive", "Neutral", "Negative"]).fillna(0).astype(int).reset_index()
    sent.columns = ["sentiment", "count"]
    color_scale = alt.Scale(
        domain=["Positive", "Neutral", "Negative"],
        range=[POS_COLOR, NEU_COLOR, NEG_COLOR],
    )
    with s1:
        sent_chart = (
            alt.Chart(sent)
            .mark_bar()
            .encode(
                x=alt.X("count:Q", title="Responses"),
                y=alt.Y("sentiment:N", sort=["Positive", "Neutral", "Negative"], title=None),
                color=alt.Color("sentiment:N", scale=color_scale, legend=None),
                tooltip=["sentiment", "count"],
            )
            .properties(height=160)
        )
        s_labels = sent_chart.mark_text(align="left", dx=4, color=GRAY).encode(text="count:Q")
        st.altair_chart(sent_chart + s_labels, use_container_width=True)
    with s2:
        pos_share = (df["sentiment"] == "Positive").mean()
        neg_share = (df["sentiment"] == "Negative").mean()
        st.metric("Positive", f"{pos_share:.0%}")
        st.metric("Negative", f"{neg_share:.0%}")
        st.caption("Net sentiment = positive − negative share.")

    st.divider()
    st.subheader("Sentiment by theme (where the pain concentrates)")
    rows = []
    for theme in THEMES:
        ts = theme_sentiment(df, theme)
        if ts["n"]:
            rows.append({"theme": theme, "Positive": ts["pos"],
                         "Negative": ts["neg"], "Neutral": ts["neu"],
                         "net": ts["net"]})
    ts_df = pd.DataFrame(rows).sort_values("net")
    melted = ts_df.melt(id_vars=["theme", "net"],
                        value_vars=["Negative", "Neutral", "Positive"],
                        var_name="sentiment", value_name="count")
    stacked = (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("count:Q", stack="normalize", title="Share of mentions", axis=alt.Axis(format="%")),
            y=alt.Y("theme:N", sort=ts_df["theme"].tolist(), title=None),
            color=alt.Color("sentiment:N", scale=color_scale,
                            legend=alt.Legend(orient="bottom", title=None)),
            order=alt.Order("sentiment:N"),
            tooltip=["theme", "sentiment", "count"],
        )
        .properties(height=320)
    )
    st.altair_chart(stacked, use_container_width=True)


def view_quant(df: pd.DataFrame):
    st.header("3 · The numbers: NPS & satisfaction by segment")
    st.caption("Net Promoter Score = % Promoters (9–10) − % Detractors (0–6).")

    seg = nps_by_segment(df)
    total_nps = overall_nps(df)

    worst = seg.loc[seg["nps"].idxmin()]
    st.markdown(
        f"#### Overall NPS is **{total_nps:+d}** — dragged down by "
        f"**{worst['segment']}** at **{worst['nps']:+d}**"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall NPS", f"{total_nps:+d}")
    for col, (_, r) in zip((c2, c3, c4), seg.iterrows()):
        col.metric(f"{r['segment']} NPS", f"{r['nps']:+d}", help=f"n={r['n']}")

    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.subheader("NPS by segment")
        seg["pos"] = seg["nps"] >= 0
        base = alt.Chart(seg)
        bars = base.mark_bar().encode(
            x=alt.X("nps:Q", title="NPS"),
            y=alt.Y("segment:N", sort=["SMB", "Mid-Market", "Enterprise"], title=None),
            color=alt.condition(alt.datum.nps < 0, alt.value(NEG_COLOR), alt.value(ACCENT)),
            tooltip=["segment", "nps", "n"],
        )
        txt = base.mark_text(align="left", dx=4, color=GRAY).encode(
            x="nps:Q",
            y=alt.Y("segment:N", sort=["SMB", "Mid-Market", "Enterprise"]),
            text=alt.Text("nps:Q", format="+d"),
        )
        st.altair_chart((bars + txt).properties(height=240), use_container_width=True)
    with right:
        st.subheader("Avg CSAT (1–5) by segment")
        csat_chart = (
            alt.Chart(seg)
            .mark_bar(color=ACCENT)
            .encode(
                x=alt.X("csat:Q", title="Mean CSAT", scale=alt.Scale(domain=[0, 5])),
                y=alt.Y("segment:N", sort=["SMB", "Mid-Market", "Enterprise"], title=None),
                tooltip=["segment", "csat"],
            )
        )
        csat_txt = csat_chart.mark_text(align="left", dx=4, color=GRAY).encode(
            text=alt.Text("csat:Q", format=".2f")
        )
        st.altair_chart((csat_chart + csat_txt).properties(height=240), use_container_width=True)

    st.divider()
    st.subheader("Segment detail")
    st.dataframe(seg[["segment", "n", "nps", "csat"]], hide_index=True, use_container_width=True)


def view_brief(df: pd.DataFrame):
    st.header("4 · One-page insight brief")
    st.caption("Auto-assembled from the analysis above — the actual deliverable.")

    freq = theme_frequency(df)
    total_nps = overall_nps(df)
    seg = nps_by_segment(df)
    worst = seg.loc[seg["nps"].idxmin()]
    top3 = freq.head(3)["theme"].tolist()

    # Most-negative themes, derived from the data (drives the headline).
    neg_themes = sorted(
        ((t, theme_sentiment(df, t)) for t in THEMES),
        key=lambda x: x[1]["net"],
    )
    pain = [t for t, ts in neg_themes if ts["net"] < 0][:2]
    if not pain:
        pain = [neg_themes[0][0]]
    pain_phrase = " and ".join(pain).lower()

    # ----- Brief container -----
    with st.container(border=True):
        st.markdown(
            f"### Customer Insights Brief — Northwind Analytics (2026-Q1)\n"
            f"*Synthetic demo study · {len(df)} respondents across "
            f"{df['segment'].nunique()} segments*"
        )

        # Headline
        pos_share = (df["sentiment"] == "Positive").mean()
        st.markdown("#### 🔎 Headline finding")
        st.markdown(
            f"> **Sentiment is broadly positive ({pos_share:.0%} of comments), but "
            f"{pain_phrase} friction is holding back advocacy — overall "
            f"NPS sits at {total_nps:+d}, and the {worst['segment']} segment lags at "
            f"{worst['nps']:+d}.** Addressing the top sources of friction is the "
            f"highest-leverage move this quarter."
        )

        st.divider()
        st.markdown("#### 📌 Three themes that matter")
        cols = st.columns(3)
        for col, theme in zip(cols, top3):
            ts = theme_sentiment(df, theme)
            fq = freq[freq["theme"] == theme].iloc[0]
            lean = ts["direction"]
            chip = {"Positive": "🟢", "Negative": "🔴"}.get(lean, "⚪")
            with col:
                st.markdown(f"**{chip} {theme}**")
                st.markdown(
                    f"`{fq['mentions']} mentions · {fq['share']:.0%} of respondents · "
                    f"net sentiment {ts['net']:+.0%}`"
                )
                st.markdown(f"> *“{ts['quote']}”*")
                st.caption(f"— synthetic {ts['quote_seg']} respondent")

        st.divider()
        st.markdown("#### ✅ Recommended actions")
        actions = _recommended_actions(freq, seg, df)
        for i, act in enumerate(actions, 1):
            st.markdown(f"**{i}.** {act}")

        st.divider()
        st.markdown(
            "#### 📊 Supporting metrics"
        )
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Overall NPS", f"{total_nps:+d}")
        m2.metric("Mean CSAT", f"{df['csat_1_5'].mean():.2f} / 5")
        m3.metric("Positive comments", f"{pos_share:.0%}")
        m4.metric("Top theme", top3[0])

    # Exportable plain-text version
    st.download_button(
        "Download brief as text",
        _brief_as_text(df, freq, seg, total_nps, worst, top3).encode("utf-8"),
        file_name="insight_brief.txt",
        mime="text/plain",
    )
    st.caption(
        "Disclaimer: all figures and quotes are synthetic and generated by "
        "data_gen.py for demonstration only."
    )


def _recommended_actions(freq: pd.DataFrame, seg: pd.DataFrame, df: pd.DataFrame):
    """Derive plain-language actions from the strongest negative themes."""
    actions = []
    # Rank themes by how negative they skew.
    neg_rank = []
    for theme in THEMES:
        ts = theme_sentiment(df, theme)
        if ts["n"]:
            neg_rank.append((theme, ts["net"], ts["n"]))
    neg_rank.sort(key=lambda x: x[1])  # most negative first

    verb = {
        "Onboarding": "Rebuild the first-run onboarding: guided setup, a 7-day success checklist, and a dedicated specialist for new accounts.",
        "Pricing": "Add pricing transparency — a value calculator and clearer renewal terms — and review the renewal step-up that finance teams flagged.",
        "Support": "Set and publish a first-response SLA, and add in-app chat so users can reach a human faster.",
        "Performance": "Prioritize performance work on large-report load times and peak-hour stability.",
        "Reliability": "Harden reliability with proactive status alerts and a visible uptime commitment.",
        "Features": "Close the top integration/export gaps on the public roadmap and communicate timelines.",
        "Usability": "Run a navigation/IA pass to cut clicks on the most common tasks.",
    }
    for theme, net, _ in neg_rank[:2]:
        if net < 0 and theme in verb:
            actions.append(verb[theme])

    worst = seg.loc[seg["nps"].idxmin()]
    actions.append(
        f"Launch a targeted save-and-grow play for the **{worst['segment']}** "
        f"segment (NPS {worst['nps']:+d}), starting with structured follow-up "
        f"interviews with detractors."
    )
    # Pad with a positive-reinforcement action if needed.
    if len(actions) < 3:
        actions.append(
            "Amplify what's working: turn promoters into references and case studies."
        )
    return actions[:4]


def _brief_as_text(df, freq, seg, total_nps, worst, top3) -> str:
    neg_themes = sorted(
        ((t, theme_sentiment(df, t)) for t in THEMES),
        key=lambda x: x[1]["net"],
    )
    pain = [t for t, ts in neg_themes if ts["net"] < 0][:2] or [neg_themes[0][0]]
    pain_phrase = " & ".join(pain).lower()
    lines = [
        "CUSTOMER INSIGHTS BRIEF — Northwind Analytics (2026-Q1)",
        "SYNTHETIC DEMO STUDY — all data fabricated by data_gen.py",
        "=" * 60,
        "",
        "HEADLINE FINDING",
        f"- Overall NPS {total_nps:+d}; {worst['segment']} lags at {worst['nps']:+d}.",
        f"- {(df['sentiment'] == 'Positive').mean():.0%} of comments positive; "
        f"{pain_phrase} friction caps advocacy.",
        "",
        "TOP THEMES",
    ]
    for theme in top3:
        ts = theme_sentiment(df, theme)
        fq = freq[freq["theme"] == theme].iloc[0]
        lines.append(f"- {theme}: {fq['mentions']} mentions ({fq['share']:.0%}), "
                     f"net sentiment {ts['net']:+.0%}")
        lines.append(f'    Quote: "{ts["quote"]}" (synthetic {ts["quote_seg"]})')
    lines += ["", "RECOMMENDED ACTIONS"]
    for i, act in enumerate(_recommended_actions(freq, seg, df), 1):
        clean = act.replace("**", "")
        lines.append(f"{i}. {clean}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def main():
    df = load_data()

    st.sidebar.title("📝 Insights Brief Builder")
    st.sidebar.caption("Customer research → decision-ready brief")
    view = st.sidebar.radio(
        "View",
        ["Research inputs", "Themes & sentiment", "Numbers (NPS/CSAT)", "Insight brief"],
    )
    st.sidebar.divider()
    st.sidebar.info(
        "**100% synthetic data.** Generated offline by `data_gen.py` "
        "(fixed seed). No real customers, companies, or APIs.",
    )
    st.sidebar.caption("Author: Leo Chan — github.com/GoldenCrate")

    if view == "Research inputs":
        view_data(df)
    elif view == "Themes & sentiment":
        view_themes(df)
    elif view == "Numbers (NPS/CSAT)":
        view_quant(df)
    else:
        view_brief(df)


if __name__ == "__main__":
    main()
