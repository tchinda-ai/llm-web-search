"""
core/variants.py — High-yield deterministic search variant generator.

Eliminates LLM latency, commentary hallucinations ("Keep it 3-6 words"),
and JSON parse failures by generating proven, domain-accurate search queries
specifically calibrated for Cameroonian, African, and global virtual event discovery.
"""

import re
from datetime import datetime

ANGLOPHONE_CITIES = {"buea", "bamenda", "limbe"}

FRANCOPHONE_CITIES = {
    "douala", "yaounde", "yaoundé", "bafoussam", "garoua", "maroua",
    "ngaoundere", "ngaoundéré", "dschang", "kribi", "edea", "édéa",
    "ebolowa", "bertoua"
}

ALL_CITIES = ANGLOPHONE_CITIES | FRANCOPHONE_CITIES | {"cameroon", "cameroun"}

# Targeted sub-keyword patterns to exact high-yield search terms
KEYWORD_RULES = [
    (
        r'\b(coding bootcamps?|bootcamps?)\b',
        [
            "bootcamp code en ligne Cameroun {year}",
            "online coding bootcamps Africa {year}",
            "virtual developer bootcamp {year} registration",
            "formation programmation web Cameroun {year}"
        ]
    ),
    (
        r'\b(hackathons?)\b',
        [
            "online tech hackathon {year} registration",
            "hackathon en ligne Cameroun {year}",
            "virtual hackathon Africa {year}",
            "developer hackathon online schedule {year}"
        ]
    ),
    (
        r'\b(cryptocurrency|crypto|blockchain|digital assets)\b',
        [
            "crypto blockchain summit Africa virtual {year}",
            "webinaire crypto finance Cameroun {year}",
            "digital assets summit online {year}",
            "sommet blockchain fintech en ligne {year}"
        ]
    ),
    (
        r'\b(fintech|banking|finance)\b',
        [
            "webinaire fintech Cameroun {year}",
            "Africa fintech webinar online {year}",
            "digital banking virtual summit {year}",
            "conférence finance numérique en ligne {year}"
        ]
    ),
    (
        r'\b(pitch|startup|entrepreneurship|entrepreneur|business)\b',
        [
            "sommet entrepreneuriat virtuel Cameroun {year}",
            "virtual startup summit Africa {year}",
            "online entrepreneur pitch competition {year}",
            "forum entrepreneuriat en ligne Afrique {year}"
        ]
    ),
    (
        r'\b(ai|artificial intelligence|intelligence artificielle|machine learning)\b',
        [
            "AI machine learning workshop online {year}",
            "atelier intelligence artificielle Cameroun {year}",
            "virtual AI masterclass Africa {year}",
            "formation IA en ligne Cameroun {year}"
        ]
    ),
    (
        r'\b(agri|agriculture|agribusiness|agro|élevage)\b',
        [
            "foire agricole Cameroun {year}",
            "salon agropastoral virtuel Cameroun {year}",
            "agribusiness webinar Africa online {year}",
            "conférence agriculture durable {year}"
        ]
    ),
]

CITY_TEMPLATES = {
    # Silicon Mountain / Buea
    "buea": [
        "Silicon Mountain tech conference Buea {year}",
        "tech meetup startups Buea {year}",
        "{topic} conference Buea {year}",
        "developer hackathon Buea {year}"
    ],
    # Economic Capital / Douala
    "douala": [
        "conférence {topic_fr} Douala {year}",
        "salon innovation {topic_fr} Douala {year}",
        "forum {topic_fr} Douala {year}",
        "meetup professionnels Douala {year}"
    ],
    # Political & University Capital / Yaoundé
    "yaounde": [
        "conférence {topic_fr} Yaoundé {year}",
        "forum national {topic_fr} Yaoundé {year}",
        "salon {topic_fr} Yaoundé {year}",
        "symposium atelier {topic_fr} Yaoundé {year}"
    ],
    "yaoundé": [
        "conférence {topic_fr} Yaoundé {year}",
        "forum national {topic_fr} Yaoundé {year}",
        "salon {topic_fr} Yaoundé {year}",
        "symposium atelier {topic_fr} Yaoundé {year}"
    ],
    # West Region Agro & University Hub / Bafoussam & Dschang
    "bafoussam": [
        "foire salon {topic_fr} Bafoussam {year}",
        "forum économique {topic_fr} Bafoussam {year}",
        "salon agropastoral Ouest Cameroun {year}",
        "conférence atelier Bafoussam {year}"
    ],
    "dschang": [
        "conférence universitaire {topic_fr} Dschang {year}",
        "forum recherche agropastoral Dschang {year}",
        "salon innovation Dschang {year}",
        "atelier formation Dschang {year}"
    ],
    # Northwest Innovation Hub / Bamenda
    "bamenda": [
        "{topic} workshop conference Bamenda {year}",
        "Bamenda innovation meetup {year}",
        "startup summit Bamenda {year}",
        "youth entrepreneurship forum Bamenda {year}"
    ],
    # Coastal & Tech / Limbe
    "limbe": [
        "tech maritime summit Limbe {year}",
        "Limbe conference meetup {year}",
        "{topic} workshop Limbe {year}",
        "innovators forum Limbe {year}"
    ],
    # Deep Seaport & Industry / Kribi
    "kribi": [
        "forum économique investissement Kribi {year}",
        "conférence {topic_fr} Kribi {year}",
        "salon développement industriel Kribi {year}",
        "rencontres professionnelles Kribi {year}"
    ],
    # Northern Hubs / Garoua & Maroua
    "garoua": [
        "forum régional {topic_fr} Garoua {year}",
        "foire agropastorale Garoua {year}",
        "salon économique Garoua {year}",
        "conférence formation Garoua {year}"
    ],
    "maroua": [
        "forum universitaire {topic_fr} Maroua {year}",
        "salon de l'innovation Maroua {year}",
        "conférence climat agropastoral Maroua {year}",
        "foire artisanat Maroua {year}"
    ],
    # Adamawa / Ngaoundéré
    "ngaoundere": [
        "forum économique universitaire Ngaoundéré {year}",
        "salon agropastoral Ngaoundéré {year}",
        "conférence atelier Ngaoundéré {year}",
        "rencontres régionales Ngaoundéré {year}"
    ],
    "ngaoundéré": [
        "forum économique universitaire Ngaoundéré {year}",
        "salon agropastoral Ngaoundéré {year}",
        "conférence atelier Ngaoundéré {year}",
        "rencontres régionales Ngaoundéré {year}"
    ],
}

TOPIC_FR_MAP = {
    "technology": "tech numérique",
    "finance": "finance fintech",
    "entrepreneurship": "entrepreneuriat startups",
    "agriculture": "agricole agropastoral",
    "education": "formation éducation",
    "health": "santé médicale",
    "climateenvironment": "climat environnement",
    "culture": "culturel artistique",
}

def generate_deterministic_variants(prompt: str) -> list[str]:
    """Deterministically generates 4 high-yield, realistic search queries for any prompt.
    
    Guarantees:
    - 0ms latency (no LLM call)
    - 0 hallucinated thinking/commentary sentences
    - Proper linguistic routing (French for Francophone Cameroon, English for Anglophone)
    - Precise event nouns and subject preservation
    """
    clean_prompt = prompt.strip()
    p_lower = clean_prompt.lower()

    # Detect target year
    year_match = re.search(r'\b202[4-9]\b', p_lower)
    year = year_match.group(0) if year_match else str(datetime.now().year)

    # Detect city / region
    detected_city = None
    for city in ALL_CITIES:
        # Match word boundary
        if re.search(rf'\b{re.escape(city)}\b', p_lower):
            detected_city = city
            break

    # Detect vertical
    detected_vertical = "technology"  # default
    for vert, fr_label in TOPIC_FR_MAP.items():
        if vert in p_lower:
            detected_vertical = vert
            break
    if "fintech" in p_lower or "bank" in p_lower:
        detected_vertical = "finance"
    elif "startup" in p_lower or "entrepreneur" in p_lower:
        detected_vertical = "entrepreneurship"
    elif "agri" in p_lower or "agro" in p_lower:
        detected_vertical = "agriculture"
    elif "health" in p_lower or "sant" in p_lower or "medic" in p_lower:
        detected_vertical = "health"
    elif "educat" in p_lower or "format" in p_lower:
        detected_vertical = "education"
    elif "climat" in p_lower or "green" in p_lower:
        detected_vertical = "climateenvironment"
    elif "cultur" in p_lower or "festiv" in p_lower or "art" in p_lower:
        detected_vertical = "culture"

    # CASE 1: Specific City in Prompt
    if detected_city and detected_city not in ("cameroon", "cameroun"):
        city_key = detected_city.lower()
        topic_fr = TOPIC_FR_MAP.get(detected_vertical, "professionnel")
        topic_en = detected_vertical

        templates = CITY_TEMPLATES.get(city_key)
        if not templates:
            # Generic Cameroon city template
            if city_key in ANGLOPHONE_CITIES:
                templates = [
                    f"{{topic}} conference {city_key.capitalize()} {{year}}",
                    f"tech meetup {city_key.capitalize()} {{year}}",
                    f"startup workshop {city_key.capitalize()} {{year}}",
                    f"annual {{topic}} events {city_key.capitalize()} {{year}}",
                ]
            else:
                templates = [
                    f"conférence {{topic_fr}} {city_key.capitalize()} {{year}}",
                    f"forum {{topic_fr}} {city_key.capitalize()} {{year}}",
                    f"salon {{topic_fr}} {city_key.capitalize()} {{year}}",
                    f"rencontres {city_key.capitalize()} {{year}}",
                ]

        results = [
            t.format(year=year, topic=topic_en, topic_fr=topic_fr)
            for t in templates[:4]
        ]
        return results

    # CASE 2: Online / Global Discovery (Matches specific keyword rules)
    for pattern, templates in KEYWORD_RULES:
        if re.search(pattern, p_lower):
            results = [t.format(year=year) for t in templates[:4]]
            return results

    # CASE 3: General National (Cameroon) or Fallback
    topic_fr = TOPIC_FR_MAP.get(detected_vertical, "tech innovation")
    topic_en = detected_vertical
    return [
        f"conférence {topic_fr} Cameroun {year}",
        f"{topic_en} conference Douala Yaounde {year}",
        f"salon forum {topic_fr} Cameroun {year}",
        f"virtual {topic_en} summit Africa {year}"
    ]
