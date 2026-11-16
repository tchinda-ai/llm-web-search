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

VERTICAL_CITY_TERMS = {
    "technology": {
        "en": ["tech conference", "hackathon", "developer meetup", "tech workshop"],
        "fr": ["conférence tech", "hackathon développeurs", "forum numérique", "atelier tech"],
    },
    "finance": {
        "en": ["fintech summit", "finance conference", "banking forum", "investment workshop"],
        "fr": ["forum fintech", "conférence finance", "salon banque", "sommet investissement"],
    },
    "entrepreneurship": {
        "en": ["startup pitch", "entrepreneurship summit", "business forum", "startup workshop"],
        "fr": ["salon entrepreneuriat", "forum startup", "concours pitch", "conférence business"],
    },
    "agriculture": {
        "en": ["agriculture summit", "agribusiness forum", "farming workshop", "agritech event"],
        "fr": ["foire agricole", "salon agropastoral", "forum agriculture", "conférence agricole"],
    },
    "education": {
        "en": ["education summit", "training workshop", "scholarship forum", "academic conference"],
        "fr": ["salon éducation", "forum formation", "conférence universitaire", "atelier formation"],
    },
    "health": {
        "en": ["health conference", "medical symposium", "public health forum", "healthcare workshop"],
        "fr": ["congrès médical", "forum santé", "conférence santé", "salon médical"],
    },
    "climateenvironment": {
        "en": ["climate summit", "renewable energy forum", "environment conference", "green workshop"],
        "fr": ["forum climat", "conférence environnement", "salon énergie", "sommet écologique"],
    },
    "culture": {
        "en": ["cultural festival", "culture event", "arts exhibition", "music festival"],
        "fr": ["festival culturel", "événement culturel", "salon culture", "rencontres culturelles"],
    },
}

CITY_DISPLAY_NAME = {
    "yaounde": "Yaoundé",
    "yaoundé": "Yaoundé",
    "ngaoundere": "Ngaoundéré",
    "ngaoundéré": "Ngaoundéré",
    "edea": "Édéa",
    "édéa": "Édéa",
}

TOPIC_FR_MAP = {
    "technology": "tech",
    "finance": "fintech",
    "entrepreneurship": "entrepreneuriat",
    "agriculture": "agricole",
    "education": "formation",
    "health": "santé",
    "climateenvironment": "climat",
    "culture": "culturel",
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
        city_label = CITY_DISPLAY_NAME.get(city_key, city_key.capitalize())
        vertical_terms = VERTICAL_CITY_TERMS.get(detected_vertical, VERTICAL_CITY_TERMS["technology"])

        if city_key in ANGLOPHONE_CITIES:
            terms = list(vertical_terms["en"])
            if city_key == "buea" and detected_vertical == "technology":
                terms[0] = "Silicon Mountain tech"
            return [f'{term} "{city_label}" {year}' for term in terms[:4]]

        # Francophone / Bilingual cities: 3 French + 1 English variant
        fr_terms = vertical_terms["fr"][:3]
        en_term = vertical_terms["en"][0]
        variants = [f'{term} "{city_label}" {year}' for term in fr_terms]
        variants.append(f'{en_term} "{city_label}" {year}')
        return variants

    # CASE 2: Online / Global Discovery (Matches specific keyword rules)
    for pattern, templates in KEYWORD_RULES:
        if re.search(pattern, p_lower):
            results = [t.format(year=year) for t in templates[:4]]
            return results

    # CASE 3: General National (Cameroon) or Fallback
    topic_fr = TOPIC_FR_MAP.get(detected_vertical, "innovation")
    topic_en = detected_vertical
    if detected_vertical == "culture":
        return [
            f'festival culturel "Cameroun" {year}',
            f'culture event "Cameroon" {year}',
            f'festival concert "Douala" {year}',
            f'exposition culturelle "Yaoundé" {year}'
        ]
    return [
        f'conférence {topic_fr} "Cameroun" {year}',
        f'{topic_en} conference "Cameroon" {year}',
        f'salon forum {topic_fr} "Douala" {year}',
        f'{topic_en} event "Yaoundé" {year}'
    ]
