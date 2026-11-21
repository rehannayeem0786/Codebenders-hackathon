"""Domain models + the profile vocabulary.

The vocabulary matters: PS5's first real question is *"how do you help a person
who does not know which details matter?"*. We answer it with
:data:`PROFILE_FIELDS` - every fact the engine can use, together with the
question to ask for it and which schemes it unlocks.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["likely_eligible", "possible", "needs_info", "not_eligible"]
RuleStatus = Literal["pass", "fail", "unknown"]
Evidence = Literal["EXTRACTED", "INFERRED", "AMBIGUOUS"]


# --------------------------------------------------------------------------- #
# vocabulary
# --------------------------------------------------------------------------- #
INCOME_BANDS = ["bpl", "low", "middle", "high"]
SOCIAL_CATEGORIES = ["sc", "st", "bc", "ebc", "obc", "minority", "general"]
OCCUPATIONS = [
    "farmer", "farm_labour", "daily_wage", "gig_worker", "artisan", "street_vendor",
    "student", "homemaker", "unemployed", "private_job", "govt_job", "retired", "self_employed",
]
HOUSE_TYPES = ["homeless", "kucha", "semi_pucca", "pucca", "rented"]
MARITAL_STATUS = ["single", "married", "widowed", "divorced", "separated"]
SECTORS = ["agriculture", "construction", "weaving", "pottery", "carpentry", "tailoring", "driver", "domestic_work", "other"]

# Categories whose "value" is risk cover: it pays out only when something goes
# wrong. Never sum these into a headline cash figure - the checklist, the impact
# report and the pitch all treat cash and cover separately, on purpose.
COVER_CATEGORIES = {"health", "insurance", "crop_insurance"}

PROFILE_FIELDS: dict[str, dict[str, Any]] = {
    "state": {"label": "State", "kind": "text", "q": "Which state do you live in?"},
    "district": {"label": "District", "kind": "text", "q": "Which district?"},
    "age": {"label": "Age", "kind": "int", "q": "How old are you?"},
    "gender": {"label": "Gender", "kind": "enum", "values": ["female", "male", "other"], "q": "Are you female, male or other?"},
    "social_category": {"label": "Social category", "kind": "enum", "values": SOCIAL_CATEGORIES,
                        "q": "Which category is on your caste certificate - SC, ST, BC, EBC, OBC, minority or general?"},
    "income_band": {"label": "Household income", "kind": "enum", "values": INCOME_BANDS,
                    "q": "Roughly what is the household income per year - under Rs 1 lakh, 1-3 lakh, 3-8 lakh, or more?"},
    "annual_income_inr": {"label": "Annual income (Rs)", "kind": "int", "q": "Any idea of the yearly income in rupees?"},
    "occupation": {"label": "Occupation", "kind": "enum", "values": OCCUPATIONS,
                   "q": "What work do you do - farming, daily wage, gig work, artisan, student, homemaker?"},
    "sector": {"label": "Trade", "kind": "enum", "values": SECTORS, "q": "Which trade - weaving, pottery, carpentry, tailoring, driving?"},
    "employment_status": {"label": "Work type", "kind": "enum", "values": ["unorganised", "organised", "unemployed", "student"],
                          "q": "Do you work in the unorganised sector (no payslip/PF)?"},
    "is_student": {"label": "Studying", "kind": "bool", "q": "Are you currently studying?"},
    "class_level": {"label": "Class/year", "kind": "text", "q": "Which class or year are you in (e.g. Class 9, B.Tech 2nd year)?"},
    "education_level": {"label": "Education", "kind": "enum", "values": ["below_8", "class_8", "class_10", "class_12", "graduate", "post_graduate"],
                        "q": "Highest class you passed?"},
    "land_acres": {"label": "Farm land (acres)", "kind": "float", "q": "Do you own farm land, and roughly how many acres?"},
    "is_widow": {"label": "Widowed", "kind": "bool", "q": "Are you a widow or widower?"},
    "disability_percent": {"label": "Disability %", "kind": "int", "q": "Do you have a disability certificate, and what percentage?"},
    "is_bpl": {"label": "BPL / white ration card", "kind": "bool", "q": "Do you have a white ration card or BPL status?"},
    "has_ration_card": {"label": "Ration card", "kind": "bool", "q": "Does the family have a ration card?"},
    "income_tax_payer": {"label": "Income-tax payer", "kind": "bool", "q": "Does anyone in the family pay income tax?"},
    "is_govt_employee": {"label": "Government employee", "kind": "bool", "q": "Is anyone in the family a government employee?"},
    "has_bank_account": {"label": "Bank account", "kind": "bool", "q": "Is there a bank account in your own name?"},
    "has_lpg_connection": {"label": "LPG connection", "kind": "bool", "q": "Does the family already have an LPG connection?"},
    "house_type": {"label": "House", "kind": "enum", "values": HOUSE_TYPES, "q": "What kind of house - own pucca, semi-pucca, kucha, rented or no house?"},
    "is_rural": {"label": "Rural", "kind": "bool", "q": "Do you live in a village or a town/city?"},
    "family_size": {"label": "Family size", "kind": "int", "q": "How many people in the family?"},
    "children_girl_under10": {"label": "Girl child under 10", "kind": "int", "q": "How many daughters under 10 years are in the family?"},
    "marital_status": {"label": "Marital status", "kind": "enum", "values": MARITAL_STATUS, "q": "Are you married, single or widowed?"},
    "wants_loan": {"label": "Needs a loan", "kind": "bool", "q": "Are you looking for a business loan?"},
    "business_type": {"label": "Business", "kind": "text", "q": "What business or shop do you run or want to start?"},
    "is_unorganised_worker": {"label": "Unorganised worker", "kind": "bool", "q": "Are you an unorganised/gig/daily-wage worker?"},
    "has_health_insurance": {"label": "Health cover", "kind": "bool", "q": "Does the family already have health insurance?"},
    "is_pregnant_or_lactating": {"label": "Pregnant/lactating", "kind": "bool", "q": "Is anyone pregnant or a new mother?"},
    "has_pucca_house": {"label": "Pucca house", "kind": "bool", "q": "Do you already own a pucca house (cement roof)? "},
    "receives_other_pension": {"label": "Any other pension", "kind": "bool", "q": "Is anyone in the family already getting a government pension?"},
    "marriage_planned": {"label": "Marriage planned", "kind": "bool", "q": "Is a marriage being planned in the family - yours or a daughter's?"},
}

# Facts that must never be collected or stored (PS5 guardrail).
FORBIDDEN_FIELDS = {
    "aadhaar", "aadhaar_number", "aadhaar_no", "pan", "pan_number", "voter_id",
    "passport_number", "bank_account_number", "ifsc", "otp", "password", "pin",
}


# --------------------------------------------------------------------------- #
# scheme data
# --------------------------------------------------------------------------- #
class Rule(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    field: str
    op: Literal[
        "eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte", "between", "true", "false",
        "exists", "class_between", "class_gte", "class_lt",
    ]
    value: Any = None
    text: str = ""
    hard: bool = True
    weight: float = 1.0
    source_note: str = ""


class SchemeDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    label: str
    mandatory: bool = True
    how_to_get: str = ""
    note: str = ""


class Deadline(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["rolling", "annual", "window", "one_time"] = "rolling"
    month_day: Optional[str] = None
    opens_month_day: Optional[str] = None
    note: str = ""


class Scheme(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    name_local: dict[str, str] = Field(default_factory=dict)
    level: Literal["central", "state", "district"] = "central"
    category: str
    summary: str
    benefit: str = ""
    benefit_value_inr: float = 0.0
    apply_url: str = ""
    portal_name: str = ""
    apply_steps: list[str] = Field(default_factory=list)
    deadline: Deadline = Field(default_factory=Deadline)
    verified_on: str = ""
    source_url: str = ""
    source_name: str = ""
    tags: list[str] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    documents: list[SchemeDocument] = Field(default_factory=list)
    # Graph provenance tag: EXTRACTED = read straight from the official source,
    # INFERRED = derived by us, AMBIGUOUS = rule changed recently / needs human check.
    provenance: Evidence = "EXTRACTED"


class SchemeBook(BaseModel):
    model_config = ConfigDict(extra="allow")

    meta: dict[str, Any] = Field(default_factory=dict)
    schemes: list[Scheme] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# requests / responses
# --------------------------------------------------------------------------- #
class Profile(BaseModel):
    """One household. Unknown facts stay ``None`` - we never guess."""

    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    notes: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    social_category: Optional[str] = None
    income_band: Optional[str] = None
    annual_income_inr: Optional[int] = None
    occupation: Optional[str] = None
    sector: Optional[str] = None
    employment_status: Optional[str] = None
    is_student: Optional[bool] = None
    class_level: Optional[str] = None
    education_level: Optional[str] = None
    land_acres: Optional[float] = None
    is_widow: Optional[bool] = None
    disability_percent: Optional[int] = None
    is_bpl: Optional[bool] = None
    has_ration_card: Optional[bool] = None
    income_tax_payer: Optional[bool] = None
    is_govt_employee: Optional[bool] = None
    has_bank_account: Optional[bool] = None
    has_lpg_connection: Optional[bool] = None
    house_type: Optional[str] = None
    is_rural: Optional[bool] = None
    family_size: Optional[int] = None
    children_girl_under10: Optional[int] = None
    marital_status: Optional[str] = None
    wants_loan: Optional[bool] = None
    business_type: Optional[str] = None
    is_unorganised_worker: Optional[bool] = None
    has_health_insurance: Optional[bool] = None
    is_pregnant_or_lactating: Optional[bool] = None
    has_pucca_house: Optional[bool] = None
    receives_other_pension: Optional[bool] = None
    marriage_planned: Optional[bool] = None

    def known(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}

    def missing(self) -> list[str]:
        return [k for k in PROFILE_FIELDS if self.model_dump().get(k) is None]


class IntakeRequest(BaseModel):
    """Plain-language or voice transcript (already PII-scrubbed on the way in)."""

    text: str = ""
    language: str = "en-IN"
    profile: Optional[Profile] = None
    use_llm: bool = True


class RuleResult(BaseModel):
    rule_id: str
    field: str
    op: str
    expected: Any = None
    actual: Any = None
    status: RuleStatus
    hard: bool = True
    weight: float = 1.0
    reason: str = ""
    rule_text: str = ""
    evidence: Evidence = "EXTRACTED"
    source_note: str = ""


class SchemeMatch(BaseModel):
    scheme_id: str
    name: str
    name_local: dict[str, str] = Field(default_factory=dict)
    level: str = "central"
    category: str = ""
    category_label: str = ""
    summary: str = ""
    benefit: str = ""
    benefit_value_inr: float = 0.0
    apply_url: str = ""
    source_url: str = ""
    source_name: str = ""
    verified_on: str = ""
    days_since_verified: Optional[int] = None
    deadline: str = ""
    verdict: Verdict = "needs_info"
    confidence: float = 0.0
    matched_rules: list[RuleResult] = Field(default_factory=list)
    failed_rules: list[RuleResult] = Field(default_factory=list)
    unknown_rules: list[RuleResult] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    unlock_questions: list[dict[str, Any]] = Field(default_factory=list)
    document_count: int = 0
    mandatory_documents: int = 0
    provenance: Evidence = "EXTRACTED"
    guardrail: str = "Likely eligible - not a guarantee. Confirm on the official portal."


class FieldQuestion(BaseModel):
    field: str
    label: str
    question: str
    kind: str = "text"
    values: list[str] = Field(default_factory=list)
    unlocks_schemes: list[str] = Field(default_factory=list)
    unlocks_count: int = 0
    unlocks_definite: int = 0
    potential_value_inr: float = 0.0
    why: str = ""


# --------------------------------------------------------------------------- #
# application tracking
# --------------------------------------------------------------------------- #
APPLICATION_STATUSES = [
    "not_started", "documents_pending", "submitted", "under_review", "approved", "rejected", "paid",
]


class Application(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    profile_id: str
    scheme_id: str
    scheme_name: str = ""
    status: str = "not_started"
    notes: str = ""
    deadline: Optional[str] = None
    documents_ready: list[str] = Field(default_factory=list)
    reference_no: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_reminder_at: Optional[str] = None


class Reminder(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    application_id: Optional[int] = None
    profile_id: str = ""
    kind: str = "deadline"  # deadline | document | follow_up
    due_on: str = ""
    message: str = ""
    channel: str = "in_app"  # in_app | whatsapp | sms
    status: str = "pending"  # pending | sent | done
    created_at: Optional[str] = None
