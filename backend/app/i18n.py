"""Local-language strings (English, Hindi, Telugu).

The audience for this build is a low-income, low-literacy household in
Telangana, so the citizen-facing text cannot be English-only. Everything the
citizen reads is looked up here; anything missing falls back to English rather
than showing a raw key name.

Only Groq/OpenRouter are used to translate *free text* on demand; the static
chrome below is pre-translated, so the demo works with no network at all.
"""
from __future__ import annotations

from typing import Any

LANGUAGES = {"en": "English", "hi": "हिन्दी", "te": "తెలుగు"}
DEFAULT_LANGUAGE = "en"

# --------------------------------------------------------------------------- #
# UI chrome
# --------------------------------------------------------------------------- #
UI: dict[str, dict[str, str]] = {
    "app.tagline": {
        "en": "Tell us about your family. We will find every government scheme you can claim, and show you why.",
        "hi": "अपने परिवार के बारे में बताइए। हम आपके हक़ की हर सरकारी योजना ढूँढकर कारण भी दिखाएँगे।",
        "te": "మీ కుటుంబం గురించి చెప్పండి. మీకు వచ్చే ప్రతి ప్రభుత్వ పథకాన్ని వెతికి, ఎందుకు వస్తుందో కూడా చూపిస్తాము.",
    },
    "nav.intake": {"en": "Tell us", "hi": "बताइए", "te": "చెప్పండి"},
    "nav.results": {"en": "Your schemes", "hi": "आपकी योजनाएँ", "te": "మీ పథకాలు"},
    "nav.graph": {"en": "Why it matched", "hi": "क्यों मिला", "te": "ఎందుకు వచ్చింది"},
    "nav.tracker": {"en": "Applications", "hi": "आवेदन", "te": "దరఖాస్తులు"},
    "nav.studio": {"en": "Rule Studio", "hi": "नियम स्टूडियो", "te": "నియమ స్టూడియో"},
    "nav.privacy": {"en": "Your privacy", "hi": "आपकी निजता", "te": "మీ గోప్యత"},
    "intake.title": {
        "en": "Speak or type, in your own words",
        "hi": "अपने शब्दों में बोलिए या लिखिए",
        "te": "మీ మాటల్లోనే మాట్లాడండి లేదా రాయండి",
    },
    "intake.placeholder": {
        "en": "Example: I am 58, a widow in Warangal. We have a white ration card and 2 acres of land. My son studies in class 9.",
        "hi": "उदाहरण: मैं 58 साल की विधवा हूँ, वारंगल से। हमारे पास सफ़ेद राशन कार्ड और 2 एकड़ ज़मीन है। बेटा कक्षा 9 में पढ़ता है।",
        "te": "ఉదాహరణ: నేను 58 ఏళ్ల విధవ, వరంగల్. మాకు తెల్ల రేషన్ కార్డు, 2 ఎకరాల భూమి ఉంది. కొడుకు 9వ తరగతి చదువుతున్నాడు.",
    },
    "intake.voice": {"en": "Speak instead", "hi": "बोलकर बताइए", "te": "మాట్లాడి చెప్పండి"},
    "intake.stop": {"en": "Stop recording", "hi": "रिकॉर्डिंग बंद करें", "te": "రికార్డింగ్ ఆపండి"},
    "intake.analyse": {"en": "Find my schemes", "hi": "मेरी योजनाएँ ढूँढें", "te": "నా పథకాలు చూపండి"},

    "intake.listening": {"en": "Listening... speak naturally.", "hi": "सुन रहे हैं... खुलकर बोलिए।", "te": "వింటున్నాము... సహజంగా మాట్లాడండి."},
    "intake.voice_note": {"en": "Record a voice note and we will transcribe it.", "hi": "वॉइस नोट रिकॉर्ड कीजिए, हम उसे लिख देंगे।", "te": "వాయిస్ నోట్ రికార్డ్ చేయండి, మేము రాసి ఇస్తాము."},
    "questions.title": {"en": "Answer these first - they unlock the most", "hi": "पहले ये बताइए - इनसे सबसे ज़्यादा मिलेगा", "te": "ముందు ఇవి చెప్పండి - వీటితో ఎక్కువ వస్తుంది"},
    "results.title": {"en": "Schemes you can claim", "hi": "आपके हक़ की योजनाएँ", "te": "మీకు వచ్చే పథకాలు"},
    "results.why": {"en": "Why this matched", "hi": "यह क्यों मिला", "te": "ఇది ఎందుకు వచ్చింది"},
    "results.unlock": {"en": "What else to tell us", "hi": "और क्या बताना है", "te": "ఇంకా ఏమి చెప్పాలి"},
    "results.documents": {"en": "Documents to keep ready", "hi": "तैयार रखने वाले कागज़", "te": "సిద్ధంగా ఉంచాల్సిన పత్రాలు"},
    "results.apply": {"en": "How to apply, step by step", "hi": "कैसे आवेदन करें, चरण-दर-चरण", "te": "ఎలా దరఖాస్తు చేయాలి, దశలవారీగా"},
    "results.deadline": {"en": "Last date / window", "hi": "अंतिम तिथि", "te": "చివరి తేదీ"},
    "results.verified": {"en": "Rule checked against", "hi": "नियम की जाँच कहाँ से", "te": "నియమం ఎక్కడి నుండి తనిఖీ"},
    "results.open_portal": {"en": "Open the official portal", "hi": "सरकारी पोर्टल खोलें", "te": "అధికారిక పోర్టల్ తెరవండి"},
    "results.track": {"en": "Track this application", "hi": "इस आवेदन पर नज़र रखें", "te": "ఈ దరఖాస్తును ట్రాక్ చేయండి"},
    "results.confidence": {"en": "How sure we are", "hi": "हमारा भरोसा", "te": "మా నమ్మకం"},
    "results.year_value": {"en": "Yearly value", "hi": "सालाना मूल्य", "te": "సంవత్సర ఫలితం"},
    "privacy.title": {"en": "Your privacy is a feature here", "hi": "आपकी निजता हमारी विशेषता है", "te": "మీ గోప్యత మా ప్రత్యేకత"},
    "privacy.line": {
        "en": "We never ask for your Aadhaar number, PAN, full bank account or OTP. If you paste one by mistake, we strip it before it is saved or sent anywhere.",
        "hi": "हम कभी आधार नंबर, पैन, पूरा बैंक खाता या ओटीपी नहीं माँगते। ग़लती से भेजा गया नंबर सहेजने या कहीं भेजने से पहले हटा दिया जाता है।",
        "te": "మేము ఎప్పుడూ ఆధార్ నంబర్, పాన్, పూర్తి బ్యాంకు ఖాతా లేదా ఓటీపీ అడగము. పొరపాటున పంపినా, భద్రపరచే లేదా ఎక్కడికైనా పంపే ముందు తీసేస్తాము.",
    },
    "results.checklist": {
        "en": "Print / save the checklist",
        "hi": "जाँच-सूची छापिए या सहेजिए",
        "te": "తనిఖీ జాబితా ప్రింట్ లేదా సేవ్ చేయండి",
    },
    "results.whatsapp_share": {
        "en": "Send to WhatsApp",
        "hi": "व्हाट्सएप पर भेजें",
        "te": "వాట్సాప్‌కు పంపండి",
    },
    "results.qr_code": {
        "en": "QR Code for Mobile",
        "hi": "मोबाइल के लिए क्यूआर",
        "te": "మొబైల్ కోసం క్యూఆర్",
    },
    "results.readiness": {
        "en": "Document Readiness",
        "hi": "दस्तावेज़ तैयारी",
        "te": "పత్రాల సంసిద్ధత",
    },
    "mode.citizen": {
        "en": "Citizen Mode",
        "hi": "नागरिक मोड",
        "te": "పౌర మోడ్",
    },
    "mode.kiosk": {
        "en": "MeeSeva Kiosk",
        "hi": "मीसेवा कियोस्क",
        "te": "మీసేవ కియోస్క్",
    },
    "tracker.whatsapp_preview": {
        "en": "Preview WhatsApp Reminder",
        "hi": "व्हाट्सएप अलर्ट देखें",
        "te": "వాట్సాప్ అలర్ట్ ప్రివ్యూ",
    },
    "results.copy": {
        "en": "Copy checklist text (WhatsApp)",
        "hi": "सूची की तैयार टेक्स्ट कॉपी करें (व्हाट्सएप)",
        "te": "జాబితా వచనం కాపీ చేయండి (వాట్సాప్)",
    },
    "results.calendar": {
        "en": "Add the deadlines to my calendar",
        "hi": "अंतिम तिथियाँ कैलेंडर में जोड़ें",
        "te": "గడువు తేదీలను క్యాలెండర్‌లో చేర్చండి",
    },
    "privacy.rights_title": {
        "en": "Your data, your rights",
        "hi": "आपका डेटा, आपके अधिकार",
        "te": "మీ డేటా, మీ హక్కులు",
    },
    "privacy.notice_loading": {
        "en": "Loading the consent notice",
        "hi": "सहमति सूचना लोड हो रही है",
        "te": "సమ్మతి నోటీసు లోడ్ అవుతోంది",
    },
    "privacy.export": {
        "en": "Download my data (JSON)",
        "hi": "मेरा डेटा डाउनलोड करें (JSON)",
        "te": "నా డేటా డౌన్‌లోడ్ చేయండి (JSON)",
    },
    "privacy.erase": {
        "en": "Delete this household",
        "hi": "यह परिवार मिटाइए",
        "te": "ఈ కుటుంబాన్ని తొలగించండి",
    },
    "privacy.sweep": {
        "en": "Run the retention sweep",
        "hi": "रिटेंशन सफ़ाई चलाइए",
        "te": "రిటెన్షన్ శుభ్రత నడపండి",
    },
    "consent.agree": {
        "en": "I agree to these details being used to check my eligibility",
        "hi": "मैं सहमत हूँ कि ये विवरण मेरी पात्रता जाँचने के लिए उपयोग हों",
        "te": "ఈ వివరాలు నా అర్హత తనిఖీకి వాడటానికి నేను అంగీకరిస్తున్నాను",
    },
    "privacy.redacted": {"en": "Removed before saving", "hi": "सहेजने से पहले हटाया", "te": "భద్రపరచే ముందు తీసేశాము"},
    "tracker.title": {"en": "Where each application stands", "hi": "हर आवेदन कहाँ तक पहुँचा", "te": "ప్రతి దరఖాస్తు ఎంతవరకు ఉంది"},
    "tracker.reminder": {"en": "Remind me", "hi": "मुझे याद दिलाएँ", "te": "నాకు గుర్తు చేయండి"},
    "studio.title": {"en": "Rule Studio - change a rule, watch the result move", "hi": "नियम स्टूडियो - नियम बदलिए, नतीजा देखिए", "te": "నియమ స్టూడియో - నియమం మార్చండి, ఫలితం చూడండి"},
    "studio.simulate": {"en": "Simulate", "hi": "अनुमान लगाइए", "te": "అంచనా వేయండి"},
    "studio.impact": {"en": "Impact on everyone below", "hi": "नीचे सब पर असर", "te": "కింద ఉన్న అందరిపై ప్రభావం"},
    "common.not_guarantee": {
        "en": "Likely eligible means our checks passed - it is not a guarantee. The final decision is the department's.",
        "hi": "संभावित पात्र का मतलब जाँच पास हुई - यह गारंटी नहीं है। अंतिम निर्णय विभाग का है।",
        "te": "అర్హత ఉండే అవకాశం అంటే మా పరీక్షలు పాస్ అయ్యాయి - ఇది హామీ కాదు. తుది నిర్ణయం శాఖదే.",
    },
    "common.missing": {"en": "Not answered yet", "hi": "अभी नहीं बताया", "te": "ఇంకా చెప్పలేదు"},
    "common.yes": {"en": "Yes", "hi": "हाँ", "te": "అవును"},
    "common.no": {"en": "No", "hi": "नहीं", "te": "కాదు"},
}

VERDICT_LABELS: dict[str, dict[str, str]] = {
    "likely_eligible": {"en": "Likely eligible", "hi": "संभावित पात्र", "te": "అర్హత ఉండే అవకాశం"},
    "possible": {"en": "Possible - one condition to check", "hi": "संभव - एक शर्त जाँचनी है", "te": "సాధ్యం - ఒక షరతు చూడాలి"},
    "needs_info": {"en": "Answer a few questions", "hi": "कुछ सवालों के जवाब दीजिए", "te": "కొన్ని ప్రశ్నలకు జవాబు చెప్పండి"},
    "not_eligible": {"en": "Not eligible right now", "hi": "अभी पात्र नहीं", "te": "ఇప్పుడు అర్హత లేదు"},
}


# --------------------------------------------------------------------------- #
# the facts we ask for, in the citizen's language
# --------------------------------------------------------------------------- #
FIELD_QUESTIONS: dict[str, dict[str, str]] = {
    "age": {"en": "How old are you?", "hi": "आपकी उम्र कितनी है?", "te": "మీ వయస్సు ఎంత?"},
    "gender": {
        "en": "Are you female, male or other?",
        "hi": "आप महिला, पुरुष या अन्य हैं?",
        "te": "మీరు స్త్రీ, పురుషుడు లేదా ఇతరులా?",
    },
    "state": {
        "en": "Which state do you live in?",
        "hi": "आप किस राज्य में रहते हैं?",
        "te": "మీరు ఏ రాష్ట్రంలో నివసిస్తున్నారు?",
    },
    "district": {"en": "Which district?", "hi": "कौन सा ज़िला?", "te": "ఏ జిల్లా?"},
    "social_category": {
        "en": "Which category is on your caste certificate - SC, ST, BC, EBC, OBC, minority or general?",
        "hi": "आपके जाति प्रमाण पत्र में कौन सा वर्ग है - एससी, एसटी, बीसी, ईबीसी, ओबीसी, अल्पसंख्यक या सामान्य?",
        "te": "మీ కుల ధృవీకరణ పత్రంలో ఏ విభాగం ఉంది - ఎస్సీ, ఎస్టీ, బీసీ, ఈబీసీ, ఓబీసీ, మైనారిటీ లేదా జనరల్?",
    },
    "income_band": {
        "en": "Roughly the household income a year - under Rs 1 lakh, 1-3 lakh, 3-8 lakh or more?",
        "hi": "सालाना घरेलू आय लगभग कितनी - 1 लाख से कम, 1-3 लाख, 3-8 लाख, या ज़्यादा?",
        "te": "సంవత్సరానికి కుటుంబ ఆదాయం సుమారుగా - లక్ష లోపు, 1-3 లక్షలు, 3-8 లక్షలు, అంతకంటే ఎక్కువ?",
    },
    "annual_income_inr": {
        "en": "Any idea of the yearly income in rupees?",
        "hi": "सालाना आय रुपये में पता है?",
        "te": "సంవత్సర ఆదాయం రూపాయల్లో తెలుసా?",
    },
    "occupation": {
        "en": "What work do you do - farming, daily wage, gig work, artisan, student, homemaker?",
        "hi": "आप क्या काम करते हैं - खेती, दिहाड़ी, गिग काम, हस्तशिल्प, छात्र, गृहिणी?",
        "te": "మీరు ఏ పని చేస్తారు - వ్యవసాయం, రోజువారీ కూలీ, గిగ్ పని, చేతివృత్తి, విద్యార్థి, గృహిణి?",
    },
    "is_student": {
        "en": "Are you currently studying?",
        "hi": "आप अभी पढ़ाई कर रहे हैं?",
        "te": "మీరు ఇప్పుడు చదువుతున్నారా?",
    },
    "class_level": {
        "en": "Which class or year are you in (e.g. Class 9)?",
        "hi": "कौन सी कक्षा या वर्ष (जैसे कक्षा 9)?",
        "te": "ఏ తరగతి లేదా ఏ సంవత్సరం (ఉదా. 9వ తరగతి)?",
    },
    "education_level": {
        "en": "Highest class you passed?",
        "hi": "अब तक पढ़ी सबसे ऊँची कक्षा?",
        "te": "ఇప్పటివరకు చదివిన అత్యధిక తరగతి?",
    },
    "land_acres": {
        "en": "Do you own farm land, and roughly how many acres?",
        "hi": "आपके पास खेती की ज़मीन है, लगभग कितने एकड़?",
        "te": "మీకు సొంత వ్యవసాయ భూమి ఉందా, సుమారు ఎన్ని ఎకరాలు?",
    },
    "is_widow": {
        "en": "Are you a widow or widower?",
        "hi": "आप विधवा या विधुर हैं?",
        "te": "మీరు విధవ లేదా వితంతువా?",
    },
    "disability_percent": {
        "en": "Do you have a disability certificate, and what percentage?",
        "hi": "आपके पास दिव्यांगता प्रमाण पत्र है, कितना प्रतिशत?",
        "te": "మీకు దివ్యాంగత ధృవీకరణ పత్రం ఉందా, ఎంత శాతం?",
    },
    "has_ration_card": {
        "en": "Does the family have a ration card?",
        "hi": "परिवार के पास राशन कार्ड है?",
        "te": "కుటుంబానికి రేషన్ కార్డు ఉందా?",
    },
    "is_bpl": {
        "en": "Do you have a white ration card or BPL status?",
        "hi": "सफ़ेद राशन कार्ड या बीपीएल है?",
        "te": "తెల్ల రేషన్ కార్డు లేదా బీపీఎల్ ఉందా?",
    },
    "income_tax_payer": {
        "en": "Does anyone in the family pay income tax?",
        "hi": "परिवार में कोई आयकर देता है?",
        "te": "కుటుంబంలో ఎవరైనా ఆదాయపు పన్ను కడతారా?",
    },
    "is_govt_employee": {
        "en": "Is anyone in the family a government employee?",
        "hi": "परिवार में कोई सरकारी कर्मचारी है?",
        "te": "కుటుంబంలో ఎవరైనా ప్రభుత్వ ఉద్యోగి ఉన్నారా?",
    },
    "has_bank_account": {
        "en": "Is there a bank account in your own name?",
        "hi": "आपके नाम पर बैंक खाता है?",
        "te": "మీ పేరుపై బ్యాంకు ఖాతా ఉందా?",
    },
    "has_lpg_connection": {
        "en": "Does the family already have an LPG gas connection?",
        "hi": "परिवार के पास पहले से एलपीजी गैस कनेक्शन है?",
        "te": "కుటుంబానికి ఇప్పటికే ఎల్పీజీ గ్యాస్ కనెక్షన్ ఉందా?",
    },
    "house_type": {
        "en": "What kind of house - own pucca, semi-pucca, kucha, rented, or no house?",
        "hi": "घर कैसा है - पक्का, अर्ध-पक्का, कच्चा, किराए का, या घर नहीं?",
        "te": "ఇల్లు ఎలాంటిది - పక్కా, పాక్షిక పక్కా, పూరి, అద్దె, లేదా ఇల్లు లేదు?",
    },
    "is_rural": {
        "en": "Do you live in a village or a town/city?",
        "hi": "आप गाँव में रहते हैं या शहर में?",
        "te": "మీరు గ్రామంలో లేదా పట్టణంలో నివసిస్తున్నారు?",
    },
    "family_size": {
        "en": "How many people are in the family?",
        "hi": "परिवार में कितने लोग हैं?",
        "te": "కుటుంబంలో ఎంతమంది ఉన్నారు?",
    },
    "marital_status": {
        "en": "Are you married, single or widowed?",
        "hi": "आप विवाहित, अविवाहित या विधवा हैं?",
        "te": "మీరు వివాహిత, అవివాహిత లేదా విధవా?",
    },
    "is_unorganised_worker": {
        "en": "Are you an unorganised, gig or daily-wage worker?",
        "hi": "आप असंगठित, गिग या दिहाड़ी मज़दूर हैं?",
        "te": "మీరు అసంఘటిత, గిగ్ లేదా రోజువారీ కూలీ కార్మికులా?",
    },
    "has_health_insurance": {
        "en": "Does the family already have health insurance?",
        "hi": "परिवार के पास पहले से स्वास्थ्य बीमा है?",
        "te": "కుటుంబానికి ఇప్పటికే ఆరోగ్య బీమా ఉందా?",
    },
    "children_girl_under10": {
        "en": "How many daughters under 10 years are in the family?",
        "hi": "परिवार में 10 साल से छोटी कितनी बेटियाँ हैं?",
        "te": "కుటుంబంలో 10 ఏళ్ల లోపు ఎంతమంది ఆడపిల్లలు ఉన్నారు?",
    },
    "is_pregnant_or_lactating": {
        "en": "Is anyone pregnant or a new mother?",
        "hi": "कोई गर्भवती या नई माँ है?",
        "te": "ఎవరైనా గర్భవతి లేదా కొత్త తల్లి ఉన్నారా?",
    },
    "receives_other_pension": {
        "en": "Is anyone already getting a government pension?",
        "hi": "किसी को पहले से सरकारी पेंशन मिल रही है?",
        "te": "ఎవరైనా ఇప్పటికే ప్రభుత్వ పెన్షన్ తీసుకుంటున్నారా?",
    },
    "has_pucca_house": {
        "en": "Do you already own a pucca house (cement roof)?",
        "hi": "आपके पास पक्का मकान (सीमेंट छत) है?",
        "te": "మీకు ఇప్పటికే పక్కా ఇల్లు (సిమెంట్ పైకప్పు) ఉందా?",
    },
    "marriage_planned": {
        "en": "Is a marriage being planned in the family - yours or a daughter's?",
        "hi": "परिवार में शादी की तैयारी है - आपकी या बेटी की?",
        "te": "కుటుంబంలో పెళ్లి జరగబోతోందా - మీదా లేదా కూతురుదా?",
    },
    "wants_loan": {
        "en": "Are you looking for a business loan?",
        "hi": "आप व्यापार के लिए कर्ज़ चाहते हैं?",
        "te": "మీరు వ్యాపార రుణం కోరుకుంటున్నారా?",
    },
    "business_type": {
        "en": "What business or shop do you run or want to start?",
        "hi": "आप कौन सा व्यापार या दुकान चलाते हैं या शुरू करना चाहते हैं?",
        "te": "మీరు ఏ వ్యాపారం లేదా దుకాణం నడుపుతున్నారు, లేదా మొదలుపెట్టాలనుకుంటున్నారు?",
    },
    "sector": {
        "en": "Which trade - weaving, pottery, carpentry, tailoring, driving?",
        "hi": "कौन सा काम - बुनाई, कुम्हारी, बढ़ईगीरी, दर्ज़ी, ड्राइविंग?",
        "te": "ఏ వృత్తి - నేత, కుమ్మరి, వడ్రంగి, దర్జీ, డ్రైవింగ్?",
    },
    "employment_status": {
        "en": "Do you work in the unorganised sector (no payslip or PF)?",
        "hi": "आप असंगठित क्षेत्र में काम करते हैं (पे-स्लिप या पीएफ नहीं)?",
        "te": "మీరు అసంఘిత రంగంలో పని చేస్తున్నారా (పే-స్లిప్ లేదా పీఎఫ్ లేదు)?",
    },
}

CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "farmer_income": {"en": "Farmer income support", "hi": "किसान आय सहायता", "te": "రైతు ఆదాయ సహాయం"},
    "crop_insurance": {"en": "Crop insurance", "hi": "फ़सल बीमा", "te": "పంట బీమా"},
    "health": {"en": "Health cover", "hi": "स्वास्थ्य सुरक्षा", "te": "ఆరోగ్య రక్షణ"},
    "education": {"en": "Scholarships and education", "hi": "छात्रवृत्ति और शिक्षा", "te": "స్కాలర్‌షిప్, విద్య"},
    "pension": {"en": "Pensions", "hi": "पेंशन", "te": "పెన్షన్లు"},
    "housing": {"en": "Housing", "hi": "आवास", "te": "ఇళ్లు"},
    "energy": {"en": "Clean cooking fuel", "hi": "स्वच्छ रसोई गैस", "te": "పరిశుభ్ర వంట గ్యాస్"},
    "savings": {"en": "Small savings", "hi": "लघु बचत", "te": "చిన్న పొదుపు"},
    "credit": {"en": "Credit and loans", "hi": "ऋण और कर्ज़", "te": "రుణాలు"},
    "enterprise": {"en": "Livelihood and enterprise", "hi": "आजीविका और उद्यम", "te": "జీవనోపాధి, వ్యాపారం"},
    "insurance": {"en": "Life and accident cover", "hi": "जीवन और दुर्घटना बीमा", "te": "జీవిత, ప్రమాద బీమా"},
    "employment": {"en": "Worker registration", "hi": "श्रमिक पंजीकरण", "te": "కార్మికుల నమోదు"},
    "marriage": {"en": "Marriage assistance", "hi": "विवाह सहायता", "te": "పెళ్లి సహాయం"},
}


# --------------------------------------------------------------------------- #
# lookup helpers
# --------------------------------------------------------------------------- #
def normalise(lang: str | None) -> str:
    """``te-IN``/``Telugu`` -> ``te``; anything unknown -> English."""
    code = (lang or "").strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def _pick(table: dict[str, dict[str, str]], key: str, lang: str) -> str:
    entry = table.get(key)
    if not entry:
        return ""
    return entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or next(iter(entry.values()), "")


def t(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Translated UI string, falling back to English, then to the key itself."""
    code = normalise(lang)
    return _pick(UI, key, code) or key


def verdict_label(verdict: str, lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(VERDICT_LABELS, verdict, normalise(lang)) or verdict


def category_label(category: str, lang: str = DEFAULT_LANGUAGE, fallback: str = "") -> str:
    return _pick(CATEGORY_LABELS, category, normalise(lang)) or fallback or category


def field_question(field: str, lang: str = DEFAULT_LANGUAGE, fallback: str = "") -> str:
    translated = _pick(FIELD_QUESTIONS, field, normalise(lang))
    if translated:
        return translated
    if fallback:
        return fallback
    from .models import PROFILE_FIELDS  # local import keeps module import order simple

    meta = PROFILE_FIELDS.get(field, {})
    return str(meta.get("q") or field.replace("_", " "))


def payload(lang: str = DEFAULT_LANGUAGE) -> dict[str, Any]:
    """Everything the frontend needs to render itself in one language."""
    code = normalise(lang)
    return {
        "language": code,
        "languages": LANGUAGES,
        "ui": {key: t(key, code) for key in UI},
        "verdicts": {key: verdict_label(key, code) for key in VERDICT_LABELS},
        "categories": {key: category_label(key, code) for key in CATEGORY_LABELS},
        "field_questions": {key: field_question(key, code) for key in FIELD_QUESTIONS},
    }
