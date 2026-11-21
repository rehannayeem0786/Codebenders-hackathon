"""Messy human input -> structured :class:`Profile`.

Two extractors work together, and the deterministic one always wins:

1. **Rules first** (:func:`extract`) - regex + keyword tables with English,
   Hindi and Telugu variants. It never hallucinates: if the phrase is not
   there, the fact stays unknown.
2. **LLM second** - fills only the gaps the rules left, in JSON mode, and only
   when a Groq/OpenRouter key is configured. Anything it returns is rechecked
   against :data:`PROFILE_FIELDS` and PII-scrubbed.

Either way the citizen is told *where* each fact came from, which matters
because PS5 demands that the reasoning be explainable.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from . import i18n, llm, pii
from .models import PROFILE_FIELDS, Profile

# --------------------------------------------------------------------------- #
# keyword tables (English / Hindi / Telugu)
# --------------------------------------------------------------------------- #
OCCUPATION_KEYWORDS: list[tuple[str, list[str]]] = [
    ("farmer", ["farmer", "farming", "agricultur", "cultivat", "kisan", "किसान", "खेती", "రైతు", "వ్యవసాయ"]),
    ("farm_labour", ["farm labour", "farm labor", "खेत मज़दूर", "खेतिहर मज़दूर", "వ్యవసాయ కూలీ"]),
    ("daily_wage", ["daily wage", "daily-wage", "daily wager", "coolie", "मज़दूरी", "मजदूरी", "दिहाड़ी", "రోజువారీ కూలీ", "కూలీ"]),
    ("gig_worker", ["gig", "delivery boy", "swiggy", "zomato", "uber", "ola", "auto driver", "driver", "ड्राइवर", "డ్రైవర్"]),
    ("artisan", ["artisan", "weaver", "handloom", "potter", "carpenter", "tailor", "barber", "बुनकर", "कुम्हार", "बढ़ई", "दर्ज़ी", "నేత", "కుమ్మరి", "వడ్రంగి", "దర్జీ"]),
    ("street_vendor", ["vendor", "hawker", "street vendor", "thela", "फेरीवाला", "रेहड़ी", "వీధి వ్యాపారి", "బండి వ్యాపారి"]),
    ("student", ["student", "studying", "studies in", "school", "college", "छात्र", "विद्यार्थी", "पढ़ता", "విద్యార్థి", "చదువుత"]),
    ("homemaker", ["homemaker", "housewife", "गृहिणी", "గృహిణి"]),
    ("retired", ["retired", "सेवानिवृत्त", "रिटायर", "పదవీ విరమణ", "రిటైర్"]),
    ("private_job", ["private job", "private company", "नौकरी", "ప్రైవేట్ ఉద్యోగం"]),
    ("self_employed", ["self employed", "my shop", "my business", "दुकान", "వ్యాపారం", "దుకాణం"]),
]

SECTOR_KEYWORDS: list[tuple[str, list[str]]] = [
    ("weaving", ["weav", "handloom", "loom", "बुनाई", "నేత", "మగ్గం"]),
    ("pottery", ["potter", "clay", "कुम्हार", "కుమ్మరి"]),
    ("carpentry", ["carpenter", "furniture", "बढ़ई", "వడ్రంగి"]),
    ("tailoring", ["tailor", "stitch", "दर्ज़ी", "దర్జీ"]),
    ("driver", ["driver", "auto", "cab", "ड्राइवर", "డ్రైవర్"]),
    ("domestic_work", ["domestic", "maid", "घरेलू काम", "ఇంటి పని"]),
    ("construction", ["construction", "building work", "निर्माण", "నిర్మాణ"]),
    ("agriculture", ["farm", "crop", "खेती", "వ్యవసాయ", "పంట"]),
]

CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("sc", ["scheduled caste", "scheduled castes", "sc", "एससी", "अनुसूचित जाति", "ఎస్సీ", "షెడ్యూల్డ్ కుల"]),
    ("st", ["scheduled tribe", "scheduled tribes", "st", "एसटी", "अनुसूचित जनजाति", "ఎస్టీ", "గిరిజన"]),
    ("ebc", ["economically backward", "ebc", "ईबीसी", "ఈబీసీ"]),
    ("bc", ["backward class", "backward classes", "bc", "बीसी", "पिछड़ा वर्ग", "బీసీ"]),
    ("obc", ["obc", "other backward", "ओबीसी", "ఓబీసీ"]),
    ("minority", ["minority", "muslim", "christian", "अल्पसंख्यक", "मुस्लिम", "మైనారిటీ", "ముస్లిం"]),
    ("general", ["general category", "general caste", "सामान्य", "జనరల్"]),
]

# Phrases that mean "yes, this is true for me".
BOOLEAN_KEYWORDS: dict[str, list[str]] = {
    "has_ration_card": ["ration card", "राशन कार्ड", "రేషన్ కార్డు", "రేషన్ కార్డ్"],
    "is_bpl": ["bpl", "white card", "white ration", "बीपीएल", "తెల్ల రేషన్", "బీపీఎల్"],
    "is_widow": ["widow", "widowed", "विधवा", "विधुर", "విధవ", "వితంతువు"],
    "has_lpg_connection": ["lpg", "gas connection", "cylinder", "गैस कनेक्शन", "సిలిండర్", "గ్యాస్"],
    "has_bank_account": ["bank account", "bank passbook", "जन धन", "बैंक खाता", "బ్యాంకు ఖాతా"],
    "is_student": ["studying", "student", "goes to school", "पढ़ता", "छात्र", "విద్యార్థి", "చదువుత"],
    "is_govt_employee": ["government employee", "govt employee", "govt job", "government job", "सरकारी नौकरी", "सरकारी कर्मचारी", "ప్రభుత్వ ఉద్యోగి"],
    "income_tax_payer": ["income tax", "pays tax", "आयकर", "टैक्स भरता", "ఆదాయపు పన్ను", "పన్ను కడతారు"],
    "is_unorganised_worker": ["unorganised", "unorganized", "no pf", "no payslip", "असंगठित", "అసంఘటిత"],
    "receives_other_pension": ["already getting pension", "receiving pension", "पेंशन मिल रही", "పెన్షన్ అందుతోంది"],
    "has_pucca_house": ["pucca house", "pakka house", "cement house", "पक्का मकान", "పక్కా ఇల్లు"],
    "marriage_planned": ["marriage", "wedding", "shaadi", "शादी", "विवाह", "పెళ్లి", "వివాహం"],
    "is_pregnant_or_lactating": ["pregnant", "expecting", "new mother", "गर्भवती", "గర్భవతి"],
    "wants_loan": ["loan", "business loan", "कर्ज़", "कर्ज", "ऋण", "రుణం", "అప్పు"],
    "has_health_insurance": ["health insurance", "medical insurance", "स्वास्थ्य बीमा", "ఆరోగ్య బీమా"],
}

# Negation markers. If one appears just before a keyword, the fact is False.
NONE_WORDS = [
    "no ", "not ", "don't", "dont", "doesn't", "doesnt", "without", "none", "never",
    "nahi", "नहीं", "बिना", "लेना", "ledu", "లేదు", "లేని", "లేదు",
]

# Gender keywords. Matched through the boundary-aware helper, never with a raw
# \b pattern: Indic vowel signs are not word characters, so \b silently fails.
FEMALE_WORDS = ["female", "woman", "lady", "widow", "girl", "महिला", "औरत", "स्त्री", "మహిళ", "స్త్రీ", "ఆడ"]
MALE_WORDS = ["male", "man", "पुरुष", "పురుషుడు", "మగ"]

STATE_NAMES = [
    "telangana", "andhra pradesh", "andhra", "karnataka", "maharashtra", "tamil nadu",
    "kerala", "odisha", "orissa", "gujarat", "rajasthan", "madhya pradesh", "uttar pradesh",
    "bihar", "west bengal", "jharkhand", "chhattisgarh", "punjab", "haryana", "delhi",
]

TELANGANA_DISTRICTS = [
    "hyderabad", "warangal", "hanamkonda", "karimnagar", "khammam", "nizamabad", "nalgonda",
    "adilabad", "mahabubnagar", "mahbubnagar", "medak", "rangareddy", "ranga reddy",
    "sangareddy", "siddipet", "suryapet", "bhadradri", "kothagudem", "jagtial", "jagitial",
    "kamareddy", "mahabubabad", "mancherial", "medchal", "nagarkurnool", "narayanpet",
    "nirmal", "peddapalli", "rajanna", "wanaparthy", "yadadri", "mulugu", "bhongir",
    "gadwal", "asifabad",
]

# Local-script place names - a citizen typing in Telugu will not write "Warangal".
LOCAL_PLACES: list[tuple[str, str]] = [
    ("తెలంగాణ", "Telangana"), ("तेलंगाना", "Telangana"),
    ("ఆంధ్ర", "Andhra Pradesh"), ("आंध्र", "Andhra Pradesh"),
    ("హైదరాబాద్", "Hyderabad"), ("हैदराबाद", "Hyderabad"),
    ("వరంగల్", "Warangal"), ("वारंगल", "Warangal"),
    ("ఖమ్మం", "Khammam"), ("खम्मम", "Khammam"),
    ("కరీంనగర్", "Karimnagar"), ("करीमनगर", "Karimnagar"),
    ("నిజామాబాద్", "Nizamabad"), ("निजामाबाद", "Nizamabad"),
    ("నల్గొండ", "Nalgonda"), ("नलगोंडा", "Nalgonda"),
    ("ఆదిలాబాద్", "Adilabad"), ("आदिलाबाद", "Adilabad"),
    ("మహబూబ్‌నగర్", "Mahabubnagar"), ("महबूबनगर", "Mahabubnagar"),
    ("మెదక్", "Medak"), ("मेदक", "Medak"),
    ("సంగారెడ్డి", "Sangareddy"), ("सूर्यापेट", "Suryapet"), ("సూర్యాపేట", "Suryapet"),
    ("జగిత్యాల", "Jagtial"), ("जगतियाल", "Jagtial"),
    ("కామారెడ్డి", "Kamareddy"), ("कामारेड्डी", "Kamareddy"),
    ("నిర్మల్", "Nirmal"), ("పెద్దపల్లి", "Peddapalli"),
    ("వనపర్తి", "Wanaparthy"), ("नागरकुरनूल", "Nagarkurnool"), ("నాగర్‌కర్నూల్", "Nagarkurnool"),
    ("గద్వాల", "Gadwal"), ("మహబూబాబాద్", "Mahabubabad"), ("ములుగు", "Mulugu"),
    ("యాదాద్రి", "Yadadri"), ("సిద్దిపేట", "Siddipet"), ("सिद्दीपेट", "Siddipet"),
    ("అసిఫాబాద్", "Asifabad"), ("మంచిర్యాల", "Mancherial"),
]

STATE_LOOKUP: list[tuple[str, str]] = [
    (name, "Telangana" if name.startswith("telang") else name.title()) for name in STATE_NAMES
]
DISTRICT_LOOKUP: list[tuple[str, str]] = [(d, d.title()) for d in TELANGANA_DISTRICTS]
for _needle, _label in LOCAL_PLACES:
    if _label in {"Telangana", "Andhra Pradesh"}:
        STATE_LOOKUP.append((_needle, _label))
    else:
        DISTRICT_LOOKUP.append((_needle, _label))

HOUSE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("homeless", ["no house", "homeless", "घर नहीं", "ఇల్లు లేదు"]),
    ("kucha", ["kucha", "mud house", "thatched", "कच्चा", "పూరి ఇల్లు"]),
    ("semi_pucca", ["semi pucca", "semi-pucca", "अर्ध पक्का", "పాక్షిక పక్కా"]),
    ("pucca", ["pucca", "pakka", "cement house", "पक्का", "పక్కా"]),
    ("rented", ["rented", "on rent", "किराए", "అద్దె"]),
]

INCOME_BAND_WORDS: list[tuple[str, list[str]]] = [
    ("bpl", ["below poverty", "bpl", "very poor", "गरीबी रेखा", "बीपीएल", "బీపీఎల్", "దారిద్ర్య"]),
    ("low", ["low income", "small income", "कम आय", "తక్కువ ఆదాయం"]),
    ("middle", ["middle class", "मध्यम वर्ग", "మధ్యతరగతి"]),
]


# --------------------------------------------------------------------------- #
# small text helpers
# --------------------------------------------------------------------------- #
def _keyword_pattern(word: str) -> str:
    """Boundary-aware pattern for short ASCII tokens only.

    Indic scripts (Telugu, Devanagari) contain combining vowel signs, which are
    not word characters for Python's ``\\b`` - so a ``\\b``-anchored search for
    "రైతు" silently fails. We therefore anchor only short ASCII tokens, which is
    exactly the case we need ("st" inside "student" must not match).
    """
    escaped = re.escape(word)
    if len(word) <= 4 and word.isascii():
        return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return escaped


def _find_first(text: str, words: list[str]) -> Optional[str]:
    """Earliest keyword hit in the text (the first mention wins)."""
    best: Optional[tuple[int, str]] = None
    for word in words:
        m = re.search(_keyword_pattern(word), text, re.I)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), word)
    return best[1] if best else None


def _negated(text: str, keyword: str, before: int = 26, after: int = 18) -> bool:
    """True when a negation marker sits just before *or* just after the keyword.

    Word order differs across languages: English says "no ration card", Hindi
    says "राशन कार्ड नहीं", Telugu says "రేషన్ కార్డు లేదు".
    """
    idx = text.find(keyword.lower())
    if idx == -1:
        return False
    window = text[max(0, idx - before) : idx + len(keyword) + after]
    return any(marker.strip() and marker.strip() in window for marker in NONE_WORDS)


def _rupees(text: str) -> Optional[int]:
    """``1,20,000`` / ``1.2 lakh`` / ``80 thousand`` -> rupees as an int."""
    m = re.search(
        r"(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|thousand|k\b|हज़ार|हजार|लाख|లక్షల|వేలు)",
        text,
        re.I,
    )
    if m:
        value = float(m.group(1).replace(",", ""))
        unit = m.group(2).lower()
        if unit.startswith(("la", "लाख", "లక్ష")):
            return int(value * 100000)
        if unit.startswith("crore"):
            return int(value * 10000000)
        return int(value * 1000)
    m = re.search(r"(?:₹|rs\.?|rupees|inr)\s*(\d[\d,]{3,})", text, re.I)
    return int(m.group(1).replace(",", "")) if m else None


def _first_group(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text, re.I)
    return m.group(1) if m else None


# A fact about a relative is not a fact about the applicant: "my son studies in
# class 9" must not turn the 58-year-old widow into a Class 9 student.
RELATIVE_WORDS = [
    "son", "daughter", "child", "children", "husband", "wife", "father", "mother",
    "brother", "sister", "grandson", "granddaughter", "बेटा", "बेटी", "पति", "पत्नी",
    "पिता", "माता", "भाई", "बहन", "కొడుకు", "కూతురు", "భర్త", "భార్య",
    "తండ్రి", "తల్లి", "సోదరుడు", "సోదరి",
]


def _about_relative(text: str, keyword: str, window: int = 34) -> bool:
    """True when the keyword sits inside a clause about someone else."""
    idx = text.find(keyword.lower())
    if idx == -1:
        return False
    before = text[max(0, idx - window) : idx]
    return any(word.lower() in before for word in RELATIVE_WORDS)


# --------------------------------------------------------------------------- #
# deterministic extraction
# --------------------------------------------------------------------------- #
def extract(text: str) -> dict[str, Any]:
    """Pull facts out of free text. Never guesses - unmentioned facts stay out."""
    facts: dict[str, Any] = {}
    if not text or not text.strip():
        return facts
    low = text.lower()

    # residence ------------------------------------------------------------
    for needle, label in STATE_LOOKUP:
        if needle in low:
            facts["state"] = label
            break
    for needle, label in DISTRICT_LOOKUP:
        if needle in low:
            facts["district"] = label
            facts.setdefault("state", "Telangana")
            break

    # age / gender ---------------------------------------------------------
    age = _first_group(r"(\d{1,2})\s*(?:years?|yrs?|साल|वर्ष|ఏళ్ల|ఏళ్ళ|సంవత్సరాల)", low)
    if age is None:
        age = _first_group(r"(?:i am|i'm|im|my age is|age|aged|उम्र|వయస్సు|వయసు)\D{0,10}(\d{1,2})\b", low)
    if age and 1 <= int(age) <= 110:
        facts["age"] = int(age)
    if _find_first(low, FEMALE_WORDS):
        facts["gender"] = "female"
    elif _find_first(low, MALE_WORDS):
        facts["gender"] = "male"

    # category / occupation / trade / house --------------------------------
    for value, words in CATEGORY_KEYWORDS:
        if _find_first(low, words):
            facts["social_category"] = value
            break
    for value, words in OCCUPATION_KEYWORDS:
        hit = _find_first(low, words)
        if hit and not _about_relative(low, hit):
            facts["occupation"] = value
            break
    for value, words in SECTOR_KEYWORDS:
        if _find_first(low, words):
            facts["sector"] = value
            break
    for value, words in HOUSE_KEYWORDS:
        if _find_first(low, words):
            facts["house_type"] = value
            break

    # money ----------------------------------------------------------------
    income = _rupees(low)
    if income is None:
        near = _first_group(r"(?:income|salary|earn|ఆదాయం|आय|कमाई)\D{0,15}(\d{4,8})", low)
        if near:
            income = int(near)
    if income:
        facts["annual_income_inr"] = income
        facts["income_band"] = (
            "bpl" if income < 100000 else "low" if income < 300000 else "middle" if income < 800000 else "high"
        )
    else:
        for band, words in INCOME_BAND_WORDS:
            if _find_first(low, words):
                facts["income_band"] = band
                break

    # land / disability / family -------------------------------------------
    acres = _first_group(r"(\d+(?:\.\d+)?)\s*(?:acres?|एकड़|ఎకరాల|ఎకరా)", low)
    if acres:
        facts["land_acres"] = float(acres)
    disability = _first_group(r"(\d{1,3})\s*(?:%|percent|प्रतिशत|శాతం)", low)
    if disability and int(disability) <= 100:
        facts["disability_percent"] = int(disability)
    family = _first_group(r"(\d{1,2})\s*(?:members?|people|सदस्य|మంది)", low)
    if family:
        facts["family_size"] = int(family)
    girls = _first_group(r"(\d{1,2})\s*(?:daughters?|girls?|बेटियाँ|बेटी|ఆడపిల్లల)", low)
    if girls:
        facts["children_girl_under10"] = int(girls)

    # school (only when the clause is about the applicant, not their child) --
    class_hit = _first_group(r"(?:class|कक्षा|తరగతి)\s*(\d{1,2})", low)
    if class_hit:
        marker = _first_group(r"(class|कक्षा|తరగతి)", low) or "class"
        if not _about_relative(low, marker):
            facts["class_level"] = f"Class {class_hit}"
            facts.setdefault("is_student", True)
    course = _find_first(
        low, ["iti", "polytechnic", "diploma", "degree", "b.tech", "btech", "b.sc", "bsc", "b.com", "bcom", "intermediate", "mba", "m.tech"]
    )
    if course and not _about_relative(low, course):
        facts.setdefault("is_student", True)

    # yes/no facts ---------------------------------------------------------
    for field, words in BOOLEAN_KEYWORDS.items():
        hit = _find_first(low, words)
        if hit:
            facts[field] = not _negated(low, hit)

    # small corrections the flat tables cannot express ---------------------
    if facts.get("is_govt_employee") is True:
        facts["employment_status"] = "organised"
    if facts.get("income_tax_payer") is True:
        facts["income_band"] = "high"
    if facts.get("marriage_planned") is False:
        facts.pop("marriage_planned")
    if facts.get("is_widow") is True:
        facts.setdefault("marital_status", "widowed")
        facts.setdefault("gender", "female")
    if facts.get("is_bpl") is True:
        # A white/BPL ration card is the practical proxy for the "bpl" band.
        facts.setdefault("income_band", "bpl")
    if re.search(r"(?<![A-Za-z0-9])(village|गाँव|गांव|గ్రామ|పల్లె)", low):
        facts.setdefault("is_rural", True)
    if re.search(r"(?<![A-Za-z0-9])(city|town|शहर|నగర|పట్టణ)", low):
        facts.setdefault("is_rural", False)
    if facts.get("occupation") in {"daily_wage", "farm_labour", "gig_worker", "street_vendor", "artisan"}:
        facts.setdefault("is_unorganised_worker", True)

    return {k: v for k, v in facts.items() if v is not None}


# --------------------------------------------------------------------------- #
# optional LLM assist (fills only what the rules could not find)
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = (
    "You are the intake assistant for SchemeSetu, a government-scheme eligibility helper in India. "
    "Convert what the citizen said into a JSON object of facts. Use ONLY the keys listed. "
    "Use null when the sentence does not say - never guess. Keep values from the allowed lists. "
    "Never ask for, return or repeat Aadhaar, PAN, bank account numbers or OTPs."
)


def _schema_hint() -> str:
    lines: list[str] = []
    for key, meta in PROFILE_FIELDS.items():
        values = meta.get("values")
        kind = meta.get("kind", "text")
        suffix = f": {'|'.join(values)}" if values else ""
        lines.append(f"- {key} ({kind}{suffix})")
    return "\n".join(lines)


def _llm_extract(text: str, language: str) -> tuple[dict[str, Any], Optional[llm.LLMResult]]:
    prompt = (
        f"Allowed keys:\n{_schema_hint()}\n\n"
        f"Citizen language: {i18n.normalise(language)}\n"
        f"Citizen said:\n\"\"\"{text}\"\"\"\n\n"
        "Return only a JSON object of the keys you are sure about."
    )
    parsed, result = llm.complete_json(prompt, system=SYSTEM_PROMPT)
    if not parsed:
        return {}, result
    raw = parsed.get("facts") if isinstance(parsed.get("facts"), dict) else parsed
    simple = {
        k: v
        for k, v in raw.items()
        if isinstance(v, (str, int, float, bool)) and str(v).strip().lower() not in {"", "null", "none", "unknown"}
    }
    clean, _ = pii.sanitize_profile(simple)
    return clean, result


def merge_facts(*groups: dict[str, Any]) -> dict[str, Any]:
    """Later groups fill gaps only - the first value for a key always wins."""
    out: dict[str, Any] = {}
    for group in groups:
        for key, value in (group or {}).items():
            if key not in out and value is not None and value != "":
                out[key] = value
    return out


def interpret(
    text: str = "",
    *,
    form: Optional[dict[str, Any]] = None,
    use_llm: bool = True,
    language: str = "en",
) -> dict[str, Any]:
    """The whole intake pipeline: scrub -> rules -> LLM -> validated Profile.

    The order is deliberate. A number the citizen typed ("2 acres", "58 years")
    is read by rules, not by a model, so the eligibility verdict stays
    reproducible. The model only fills in what the rules could not see.
    """
    safe_text, findings = pii.redact(text or "")
    form_clean, form_report = pii.sanitize_profile(form or {})
    sources: dict[str, str] = {key: "form" for key in form_clean}

    rule_facts = extract(safe_text)
    for key in rule_facts:
        sources.setdefault(key, "rules")

    llm_meta: Optional[llm.LLMResult] = None
    llm_facts: dict[str, Any] = {}
    if use_llm and llm.available() and safe_text.strip():
        llm_facts, llm_meta = _llm_extract(safe_text, language)
        for key in llm_facts:
            sources.setdefault(key, "llm")

    merged = merge_facts(form_clean, rule_facts, llm_facts)
    clean, report = pii.sanitize_profile(merged)
    profile = Profile(**clean)

    redactions = [f.as_dict() for f in findings] + list(report.get("redactions", []))
    used_llm = bool(llm_meta and llm_meta.ok)
    return {
        "profile": profile,
        "facts": profile.known(),
        "field_sources": sources,
        "transcript": safe_text,
        "redactions": redactions,
        "dropped_keys": report.get("dropped_keys", []) + form_report.get("dropped_keys", []),
        "privacy_note": pii.summarise([f for f in findings]) or report.get("message", ""),
        "used_llm": used_llm,
        "method": "rules+llm" if used_llm else "rules",
        "llm": llm_meta.as_dict() if llm_meta else None,
        "notes": (
            "Facts are read with fixed rules first; the model only filled the gaps."
            if used_llm
            else "Read with fixed keyword rules - no model needed, so the same input always gives the same answer."
        ),
    }


def narrate(match: Any, language: str = "te") -> dict[str, Any]:
    """Explain one match in the citizen's own language (LLM, with fallback).

    The fallback is the deterministic ``why`` list the engine already built, so
    this is a nicety - never a dependency.
    """
    code = i18n.normalise(language)
    if match is None or code == "en" or not llm.available():
        return {"text": "", "method": "rules", "language": code}
    facts = "; ".join(match.why[:6]) if getattr(match, "why", None) else ""
    prompt = (
        f"Scheme: {match.name}\nVerdict: {i18n.verdict_label(match.verdict, 'en')}\n"
        f"Benefit: {match.benefit}\nDeadline: {match.deadline}\n"
        f"Reasons from our rule engine: {facts}\n\n"
        f"Explain this to a low-income family in {i18n.LANGUAGES.get(code, 'their language')} "
        "in at most 4 short sentences. Say 'likely eligible, not a guarantee'. "
        "Be concrete: what they get, what to keep ready, where to apply. Do not invent amounts."
    )
    text = llm.complete(prompt, max_tokens=320, temperature=0.3)
    return {"text": text or "", "method": "llm" if text else "rules", "language": code}
