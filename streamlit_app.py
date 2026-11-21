"""Streamlit entrypoint for SchemeSetu.
Enables 1-click deployment on Streamlit Community Cloud (share.streamlit.io).
Uses the exact same deterministic rule engine and curated schemes.
"""
from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent

# Configure page
st.set_page_config(
    page_title="SchemeSetu — Claim What's Yours",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject Streamlit secrets into environment variables for backend modules
import os
try:
    for k, v in st.secrets.items():
        if isinstance(v, str) and k not in os.environ:
            os.environ[k] = v
except Exception:
    pass

# Load core modules
from backend.app import rule_engine as engine
from backend.app import models, i18n, pii, intake

# Cache schemes data
@st.cache_data
def load_schemes():
    schemes_file = ROOT / "data" / "schemes.json"
    with open(schemes_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    categories = data.get("categories", {})
    schemes = [models.Scheme(**s) for s in data.get("schemes", [])]
    return schemes, categories

@st.cache_data
def load_samples():
    samples_file = ROOT / "data" / "sample_profiles.json"
    if not samples_file.exists():
        return []
    with open(samples_file, "r", encoding="utf-8") as f:
        return json.load(f).get("samples", [])

schemes, categories = load_schemes()
samples = load_samples()

# Sidebar
st.sidebar.title("◆ SchemeSetu")
st.sidebar.caption("Telangana · PS5: Citizens & Public Services")

lang = st.sidebar.selectbox("Language / భాష / भाषा", ["en", "te", "hi"], format_func=lambda x: {"en": "English", "te": "తెలుగు", "hi": "हिन्दी"}[x])

st.sidebar.markdown("---")
st.sidebar.subheader("Demo Households")
sample_titles = ["— Custom Intake —"] + [s.get("title", s["id"]) for s in samples]
selected_sample = st.sidebar.selectbox("Load sample household:", sample_titles)

default_text = ""
prefill_facts = {}
if selected_sample != "— Custom Intake —":
    s_obj = next((s for s in samples if s.get("title") == selected_sample or s["id"] == selected_sample), None)
    if s_obj:
        default_text = s_obj.get("text", "")
        prefill_facts = s_obj.get("form", {})

# Main header
st.title("SchemeSetu — Welfare Eligibility Navigator")
st.markdown("Tell us about your family in your own words. We evaluate **26 official Telangana & Central schemes** using deterministic rules with proof.")

# Status Strip
col1, col2, col3, col4 = st.columns(4)
col1.metric("Curated Schemes", f"{len(schemes)}")
col2.metric("Deterministic Rules", "123 rules")
col3.metric("PII Guardrails", "Active (Aadhaar Redaction)")
col4.metric("Engine Mode", "Deterministic (Zero Hallucination)")

st.markdown("---")

# Intake Form
with st.container():
    st.subheader("1. Household Description")
    user_text = st.text_area("Describe your family (age, occupation, income, ration card, land):", value=default_text, height=110)
    
    col_btn, col_opt = st.columns([1, 3])
    with col_btn:
        evaluate_clicked = st.button("🔍 Find My Schemes", type="primary", use_container_width=True)

if evaluate_clicked or default_text:
    # 1. PII Redaction
    redacted_text, pii_matches = pii.redact(user_text)
    if pii_matches:
        st.info(f"🛡️ **Privacy Shield Active**: Automatically redacted {len(pii_matches)} sensitive identifiers (Aadhaar/PAN/Phone) before processing.")

    # 2. Extract facts using deterministic keyword rules
    extracted_facts = intake.extract_facts_from_text(redacted_text, lang)
    # Merge with prefilled facts
    facts = {**extracted_facts, **prefill_facts}

    profile = models.Profile(**facts)

    # 3. Evaluate schemes
    pairs = [(s, engine.evaluate_scheme(s, profile, categories)) for s in schemes]
    matches = engine.rank_matches([m for _, m in pairs])

    # Calculate Cash vs Risk Cover strictly separate
    cover_categories = {"health", "insurance", "crop_insurance"}
    cash_total = sum(m.benefit_value_inr for m in matches if m.verdict == "likely_eligible" and m.category not in cover_categories and m.benefit_value_inr)
    cover_total = sum(m.benefit_value_inr for m in matches if m.verdict == "likely_eligible" and m.category in cover_categories and m.benefit_value_inr)
    
    eligible_count = sum(1 for m in matches if m.verdict == "likely_eligible")
    possible_count = sum(1 for m in matches if m.verdict == "possible")
    needs_info_count = sum(1 for m in matches if m.verdict == "needs_info")

    st.markdown("### 2. Financial Impact Scorecard")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Cash Support (DBT / yr)", f"₹{cash_total:,.0f}", help="Direct benefit transfers to bank account")
    kpi2.metric("Risk / Health Cover", f"₹{cover_total:,.0f}", help="Insurance & health coverage that pays out on an event")
    kpi3.metric("Actionable Schemes", f"{eligible_count} Eligible", f"{possible_count} Possible")
    kpi4.metric("Facts Checked", f"{len(facts)} facts extracted")

    st.markdown("---")
    st.markdown("### 3. Matched Schemes & Why You Qualify")

    filter_verdict = st.radio("Filter by status:", ["All", "Likely Eligible", "Needs Info / Possible", "Not Eligible"], horizontal=True)

    filtered_matches = []
    for m in matches:
        if filter_verdict == "Likely Eligible" and m.verdict != "likely_eligible":
            continue
        elif filter_verdict == "Needs Info / Possible" and m.verdict not in ("needs_info", "possible"):
            continue
        elif filter_verdict == "Not Eligible" and m.verdict != "not_eligible":
            continue
        filtered_matches.append(m)

    for m in filtered_matches:
        v_color = {"likely_eligible": "🟢", "possible": "🔵", "needs_info": "🟡", "not_eligible": "🔴"}.get(m.verdict, "⚪")
        v_name = i18n.verdict_label(m.verdict, lang)
        
        # Scheme Title
        local_name = ""
        if isinstance(m.name_local, dict):
            local_name = m.name_local.get(lang, "")
        elif isinstance(m.name_local, str):
            local_name = m.name_local
        
        display_title = f"{m.name} ({local_name})" if local_name and lang != "en" else m.name

        with st.expander(f"{v_color} **{display_title}** — {v_name}"):
            col_info, col_meta = st.columns([3, 1])
            with col_info:
                st.markdown(f"**Benefit:** {m.benefit}")
                st.markdown(f"**Summary:** {m.summary}")
                st.markdown(f"**Deadline:** {m.deadline}")
                if m.apply_url:
                    st.markdown(f"🔗 [Official Portal Link]({m.apply_url})")

                st.markdown("##### Why it matched (Rule-by-rule arithmetic):")
                for w in m.why:
                    if w.startswith("Pass"):
                        st.markdown(f"- ✅ <span style='color:#10b981;'>{w}</span>", unsafe_allow_html=True)
                    elif w.startswith("Not met"):
                        st.markdown(f"- ❌ <span style='color:#f43f5e;'>{w}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"- ⚠️ <span style='color:#f59e0b;'>{w}</span>", unsafe_allow_html=True)

            with col_meta:
                st.markdown(f"**Category:** `{m.category}`")
                st.markdown(f"**Level:** `{m.level}`")
                st.markdown(f"**Provenance:** `{m.provenance}`")
                st.markdown(f"**Confidence:** `{m.confidence:.2f}`")
                st.markdown(f"**Mandatory Papers:** `{m.mandatory_documents}/{m.document_count}`")

# Footer
st.markdown("---")
st.caption("SchemeSetu v2.0 · Codebenders ACE Builders Hackathon 2026 · Problem Statement 5 — 'Claim What's Yours'")
