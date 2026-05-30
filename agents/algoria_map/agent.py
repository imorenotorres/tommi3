"""
Algoria Map Agent — Interactive map explorer for UMA mobility agreements.

Accepts natural language queries, converts them to SQL filters, executes
against the destinations database, and renders results on a Leaflet map.
"""

import json
import os
import re
import sqlite3

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "web"))
from llm_client import LLMClient


# ---------------------------------------------------------------------------
# Country coordinates (lat, lon) for map markers
# ---------------------------------------------------------------------------
COUNTRY_COORDS = {
    "Albania": [41.33, 19.82], "Alemania": [51.16, 10.45], "Argelia": [28.03, 1.66],
    "Argentina": [-38.42, -63.62], "Armenia": [40.07, 45.04], "Australia": [-25.27, 133.78],
    "Austria": [47.52, 14.55], "Azerbaiyán": [40.14, 47.58], "Bélgica": [50.50, 4.47],
    "Bolivia": [-16.29, -63.59], "Brasil": [-14.24, -51.93], "Bulgaria": [42.73, 25.49],
    "Canadá": [56.13, -106.35], "Chequia": [49.82, 15.47], "Chile": [-35.68, -71.54],
    "Colombia": [4.57, -74.30], "Corea del Sur": [35.91, 127.77], "Costa Rica": [9.75, -83.75],
    "Croacia": [45.10, 15.20], "Dinamarca": [56.26, 9.50], "Ecuador": [-1.83, -78.18],
    "Eslovaquia": [48.67, 19.70], "Eslovenia": [46.15, 14.99], "España": [40.46, -3.75],
    "Estados Unidos": [37.09, -95.71], "Estonia": [58.60, 25.01], "Filipinas": [12.88, 121.77],
    "Finlandia": [61.92, 25.75], "Francia": [46.23, 2.21], "Georgia": [42.32, 43.36],
    "Grecia": [39.07, 21.82], "Honduras": [15.20, -86.24], "Hungría": [47.16, 19.50],
    "India": [20.59, 78.96], "Indonesia": [-0.79, 113.92], "Irlanda": [53.14, -7.69],
    "Islandia": [64.96, -19.02], "Italia": [41.87, 12.57], "Japón": [36.20, 138.25],
    "Kazajistán": [48.02, 66.92], "Letonia": [56.88, 24.60], "Libia": [26.34, 17.23],
    "Lituania": [55.17, 23.88], "Malasia": [4.21, 101.98], "Malta": [35.94, 14.38],
    "México": [23.63, -102.55], "Moldavia": [47.41, 28.37], "Nepal": [28.39, 84.12],
    "Noruega": [60.47, 8.47], "Países Bajos": [52.13, 5.29], "Panamá": [8.54, -80.78],
    "Paraguay": [-23.44, -58.44], "Perú": [-9.19, -75.02], "Polonia": [51.92, 19.15],
    "Portugal": [39.40, -8.22], "Puerto Rico": [18.22, -66.59],
    "Reino Unido": [55.38, -3.44], "República de Chipre": [35.13, 33.43],
    "República de Macedonia": [41.51, 21.75], "República Dominicana": [18.74, -70.16],
    "Rumanía": [45.94, 24.97], "Serbia": [44.02, 21.01], "Sudáfrica": [-30.56, 22.94],
    "Suecia": [60.13, 18.64], "Suiza": [46.82, 8.23], "Tailandia": [15.87, 100.99],
    "Taiwán": [23.70, 120.96], "Tayikistán": [38.86, 71.28], "Turquía": [38.96, 35.24],
    "Ucrania": [48.38, 31.17], "Uruguay": [-32.52, -55.77], "Venezuela": [6.42, -66.59],
}

CONTINENT_MAP = {
    "Europa": ["Albania", "Alemania", "Austria", "Azerbaiyán", "Bélgica", "Bulgaria",
               "Chequia", "Croacia", "Dinamarca", "Eslovaquia", "Eslovenia", "España",
               "Estonia", "Finlandia", "Francia", "Georgia", "Grecia", "Hungría",
               "Irlanda", "Islandia", "Italia", "Kazajistán", "Letonia", "Lituania",
               "Malta", "Moldavia", "Noruega", "Países Bajos", "Polonia", "Portugal",
               "Reino Unido", "República de Chipre", "República de Macedonia",
               "Rumanía", "Serbia", "Suecia", "Suiza", "Turquía", "Ucrania"],
    "América": ["Argentina", "Bolivia", "Brasil", "Canadá", "Chile", "Colombia",
                "Costa Rica", "Ecuador", "Estados Unidos", "Honduras", "México",
                "Panamá", "Paraguay", "Perú", "Puerto Rico", "República Dominicana",
                "Uruguay", "Venezuela"],
    "Asia": ["Armenia", "Corea del Sur", "Filipinas", "India", "Indonesia", "Japón",
             "Kazajistán", "Malasia", "Nepal", "Tailandia", "Taiwán", "Tayikistán"],
    "África": ["Argelia", "Libia", "Sudáfrica"],
    "Oceanía": ["Australia"],
}

# Reverse lookup: country → continent
COUNTRY_TO_CONTINENT = {}
for cont, countries in CONTINENT_MAP.items():
    for c in countries:
        COUNTRY_TO_CONTINENT[c] = cont

# Continent center coordinates and zoom levels
CONTINENT_VIEW = {
    "Europa": {"center": [54, 10], "zoom": 3},
    "América": {"center": [5, -75], "zoom": 2},
    "Asia": {"center": [30, 100], "zoom": 3},
    "África": {"center": [5, 20], "zoom": 3},
    "Oceanía": {"center": [-25, 134], "zoom": 4},
    "world": {"center": [15, 10], "zoom": 2},
}

# Continent name aliases (for LLM output normalization)
CONTINENT_ALIASES = {
    "europe": "Europa", "europa": "Europa",
    "america": "América", "americas": "América", "américa": "América",
    "north america": "América", "south america": "América",
    "latin america": "América", "latinoamérica": "América",
    "asia": "Asia",
    "africa": "África", "áfrica": "África",
    "oceania": "Oceanía", "oceanía": "Oceanía",
}

# Faculty short names for matching
# UNINOVIS partner universities (as they appear in destinations.db)
UNINOVIS_PARTNERS = [
    "The Hague University of Applied Sciences (THUAS)",       # THUAS
    "Université Sorbonne Paris Nord (USPN)",                  # USPN
    "UNIVERSITA DEGLI STUDI DELLA CAMPANIA LUIGI VANVITELLI", # UDCLV
    "Technical University of Applied Sciences Würzburg-Schweinfurt", # THWS
    "UNIVERSITY OF TIRANA",                                   # UT
    "KAUNO KOLEGIJA",                                         # KK
    "Tampere University of Applied Sciences",                  # TAMK
]

FACULTY_ALIASES = {
    "letters": "Filosofía y Letras", "letras": "Filosofía y Letras",
    "filosofía y letras": "Filosofía y Letras",
    "law": "Derecho", "derecho": "Derecho",
    "medicine": "Medicina", "medicina": "Medicina",
    "science": "Ciencias", "ciencias": "Ciencias",
    "economics": "Ciencias Económicas y Empresariales",
    "económicas": "Ciencias Económicas y Empresariales",
    "business": "Ciencias Económicas y Empresariales",
    "education": "Ciencias de la Educación", "educación": "Ciencias de la Educación",
    "engineering": "Ingenierías Industriales", "ingeniería": "Ingenierías Industriales",
    "industrial engineering": "Ingenierías Industriales",
    "computer science": "Ingeniería Informática", "informática": "Ingeniería Informática",
    "telecom": "Ingeniería de Telecomunicación",
    "telecomunicación": "Ingeniería de Telecomunicación",
    "telecommunications": "Ingeniería de Telecomunicación",
    "architecture": "Arquitectura", "arquitectura": "Arquitectura",
    "fine arts": "Bellas Artes", "bellas artes": "Bellas Artes",
    "communication": "Ciencias de la Comunicación",
    "comunicación": "Ciencias de la Comunicación",
    "health": "Ciencias de la Salud", "salud": "Ciencias de la Salud",
    "psychology": "Psicología y Logopedia", "psicología": "Psicología y Logopedia",
    "tourism": "Turismo", "turismo": "Turismo",
    "social work": "Estudios Sociales y del Trabajo",
    "trabajo social": "Estudios Sociales y del Trabajo",
    "marketing": "Marketing y Gestión",
}


# ---------------------------------------------------------------------------
# Tool definitions for the LLM
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_agreements",
            "description": (
                "Search mobility agreements in the database. Returns matching agreements "
                "to display on a map. All parameters are optional filters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "continent": {
                        "type": "string",
                        "description": "Filter by continent: Europa, América, Asia, África, Oceanía",
                    },
                    "country": {
                        "type": "string",
                        "description": "Filter by destination country (in Spanish, e.g. 'Italia', 'Alemania')",
                    },
                    "faculty": {
                        "type": "string",
                        "description": "Filter by UMA faculty (partial match, e.g. 'Filosofía y Letras', 'Derecho', 'Medicina')",
                    },
                    "language": {
                        "type": "string",
                        "description": "Filter by required language name (e.g. 'INGLÉS', 'FRANCÉS', 'ALEMÁN')",
                    },
                    "language_level": {
                        "type": "string",
                        "description": "Filter by required language level (e.g. 'A1', 'A2', 'B1', 'B2', 'C1', 'C2')",
                    },
                    "mobility_program": {
                        "type": "string",
                        "description": "Filter by mobility program (e.g. 'ERASMUS+ KA131', 'MOVILIDAD INTERNACIONAL UMA')",
                    },
                    "degree_level": {
                        "type": "string",
                        "description": "Filter by degree level: 'undergraduate', 'master', or 'phd'",
                    },
                    "university": {
                        "type": "string",
                        "description": "Filter by host university name (partial match)",
                    },
                    "uninovis": {
                        "type": "boolean",
                        "description": "If true, show only agreements with UNINOVIS partner universities",
                    },
                },
                "required": [],
            },
        },
    }
]

SYSTEM_PROMPT = """You are Algoria Map, an assistant that helps users explore UMA (Universidad de Málaga) mobility agreements on an interactive map.

When the user asks about agreements, call the search_agreements tool with the appropriate filters.
- For general queries like "show all agreements", call with no filters.
- For continent queries like "show Europe" or "agreements in Asia", set the continent parameter.
- For country queries like "agreements in Italy", set the country parameter (use Spanish names: Italia, Alemania, Francia, etc.).
- For faculty queries like "Faculty of Letters", set faculty to the relevant faculty name.
- For language requirements like "English B2", set language and/or language_level.
- For refinements like "show only Italy" or "only those with B2 English", apply the mentioned filter.
- For degree level filters like "only master" or "undergraduate agreements", set degree_level.

Country names in the database are in Spanish. Common mappings:
Italy=Italia, Germany=Alemania, France=Francia, Netherlands=Países Bajos, UK=Reino Unido,
Czech Republic=Chequia, South Korea=Corea del Sur, Belgium=Bélgica, USA=Estados Unidos,
Sweden=Suecia, Switzerland=Suiza, Norway=Noruega, Denmark=Dinamarca, Finland=Finlandia,
Poland=Polonia, Romania=Rumanía, Greece=Grecia, Turkey=Turquía, Portugal=Portugal,
Japan=Japón, Mexico=México, Brazil=Brasil, Argentina=Argentina, Chile=Chile, Colombia=Colombia.

Faculty short names: Letters=Filosofía y Letras, Law=Derecho, Medicine=Medicina,
Science=Ciencias, Economics/Business=Ciencias Económicas y Empresariales,
Education=Ciencias de la Educación, Engineering=Ingenierías Industriales,
Computer Science=Ingeniería Informática, Architecture=Arquitectura,
Fine Arts=Bellas Artes, Communication=Ciencias de la Comunicación,
Health=Ciencias de la Salud, Psychology=Psicología y Logopedia, Tourism=Turismo.

Language names are in Spanish uppercase: INGLÉS, FRANCÉS, ALEMÁN, ITALIANO, PORTUGUÉS, ESPAÑOL.

If the user asks about UNINOVIS partners or alliance universities, set uninovis=true.

Always call the tool — never answer from memory. The tool will generate the map."""


def _display_name(name: str) -> str:
    """Convert university name to proper title case for display."""
    if not name:
        return name
    # Fix HTML entities first
    name = name.replace("&#39;", "'").replace("&amp;", "&")
    # If not mostly uppercase, leave as-is (already mixed case)
    if sum(1 for c in name if c.isupper()) < len(name) * 0.6:
        return name
    # Title case
    result = name.title()
    # Lowercase articles, prepositions, conjunctions (multi-language)
    for word in [
        " De ", " Del ", " Della ", " Delle ", " Degli ", " Di ", " Da ",
        " Of ", " The ", " And ", " In ", " For ", " On ", " At ",
        " Y ", " E ", " El ", " La ", " Las ", " Los ", " En ",
        " Für ", " Und ", " Der ", " Des ", " Von ", " Zu ",
        " Du ", " Des ", " Et ", " Le ", " Les ", " Au ", " Aux ",
        " Do ", " Dos ", " Das ", " Na ", " No ",
        " W ", " Im ", " I ",
    ]:
        result = result.replace(word, word.lower())
    # Keep acronyms uppercase (2-4 letter words that were all caps)
    import re
    def fix_acronyms(m):
        orig = name[m.start():m.end()]
        word = m.group(0)
        if orig.isupper() and len(word.strip()) <= 5:
            return orig
        return word
    result = re.sub(r'\b[A-Z][a-z]{0,4}\b', fix_acronyms, result)
    # Ensure first character is uppercase
    if result:
        result = result[0].upper() + result[1:]
    return result


class Agent:
    def __init__(self):
        self._agent_dir = os.path.dirname(os.path.abspath(__file__))
        self._db_path = os.path.join(self._agent_dir, "data", "destinations.db")
        # LLM is optional — only needed for chat interface, not for the standalone map page
        try:
            self.client = LLMClient()
            self.model = self._get_model()
        except Exception:
            self.client = None
            self.model = None
        self._query_history = []
        self._uni_coords = self._load_university_coords()
        self._uni_websites = self._load_json("university_websites.json")
        self._config = self._load_json("../config.json")
        self._lang = self._config.get("language", "en")
        self._t = self._config.get("translations", {}).get(self._lang, {})

    def _load_json(self, filename: str) -> dict:
        path = os.path.join(self._agent_dir, "data", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_university_coords(self) -> dict:
        """Load cached university coordinates."""
        path = os.path.join(self._agent_dir, "data", "university_coords.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_model(self):
        from dotenv import dotenv_values
        env_path = os.path.join(self._agent_dir, ".env")
        if os.path.exists(env_path):
            env = dotenv_values(env_path)
            provider = env.get("LLM_PROVIDER", "").lower()
            if provider == "ollama":
                return env.get("OLLAMA_MODEL", "mistral")
            elif provider == "mistral":
                return env.get("MISTRAL_MODEL", "mistral-small-latest")
        web_env_path = os.path.join(self._agent_dir, "..", "..", "web", ".env")
        if os.path.exists(web_env_path):
            env = dotenv_values(web_env_path)
            provider = env.get("LLM_PROVIDER", "").lower()
            if provider == "ollama":
                return env.get("OLLAMA_MODEL", "mistral")
            elif provider == "mistral":
                return env.get("MISTRAL_MODEL", "mistral-small-latest")
        return "mistral-small-latest"

    # ------------------------------------------------------------------
    # Database query
    # ------------------------------------------------------------------

    def _execute_search(self, filters: dict) -> list[dict]:
        """Query destinations.db with the given filters. Returns list of dicts."""
        conditions = []
        params = []

        if filters.get("continent"):
            continent = filters["continent"]
            # Normalize
            continent = CONTINENT_ALIASES.get(continent.lower(), continent)
            countries = CONTINENT_MAP.get(continent, [])
            if countries:
                placeholders = ",".join("?" * len(countries))
                conditions.append(f"destination_country IN ({placeholders})")
                params.extend(countries)

        if filters.get("country"):
            conditions.append("destination_country LIKE ?")
            params.append(f"%{filters['country']}%")

        if filters.get("faculty"):
            conditions.append("uma_faculties LIKE ?")
            params.append(f"%{filters['faculty']}%")

        if filters.get("language"):
            lang = filters["language"].upper()
            conditions.append("(lang_1_name LIKE ? OR lang_2_name LIKE ?)")
            params.extend([f"%{lang}%", f"%{lang}%"])

        if filters.get("language_level"):
            level = filters["language_level"].upper()
            conditions.append("(lang_1_level = ? OR lang_2_level = ?)")
            params.extend([level, level])

        if filters.get("mobility_program"):
            conditions.append("mobility_program LIKE ?")
            params.append(f"%{filters['mobility_program']}%")

        if filters.get("degree_level"):
            dl = filters["degree_level"].lower()
            if "under" in dl or "grado" in dl:
                conditions.append("allows_undergraduate = 'Sí'")
            elif "master" in dl or "máster" in dl:
                conditions.append("allows_master = 'Sí'")
            elif "phd" in dl or "doctor" in dl:
                conditions.append("allows_phd = 'Sí'")

        if filters.get("university"):
            conditions.append("host_institution LIKE ?")
            params.append(f"%{filters['university']}%")

        if filters.get("uninovis"):
            placeholders = ",".join("?" * len(UNINOVIS_PARTNERS))
            conditions.append(f"host_institution IN ({placeholders})")
            params.extend(UNINOVIS_PARTNERS)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT destination_country, host_institution, destination_faculty,
                   uma_faculties, uma_degrees, mobility_program,
                   lang_1_name, lang_1_level, lang_1_cert_mandatory, lang_1_cert_details,
                   lang_2_name, lang_2_level, lang_2_cert_mandatory, lang_2_cert_details,
                   allows_undergraduate, allows_master, allows_phd,
                   min_gpa_requirement, student_vacancies, tutors,
                   start_date, end_date, agreement_id,
                   academic_requirements_text, public_comments
            FROM destinations
            WHERE {where}
            ORDER BY destination_country, host_institution
        """

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Map rendering
    # ------------------------------------------------------------------

    def _build_map_link(self, filters: dict, total: int, n_countries: int) -> str:
        """Build a markdown link that the frontend intercepts to render a Leaflet map."""
        from urllib.parse import urlencode

        filter_desc = self._describe_filters(filters)
        summary = f"{total} agreement{'s' if total != 1 else ''} in {n_countries} countr{'ies' if n_countries != 1 else 'y'}"
        if filter_desc:
            summary += f" — {filter_desc}"

        params = {k: v for k, v in filters.items() if v}
        url = f"/api/agents/algoria_map/agreements-map?{urlencode(params)}" if params else "/api/agents/algoria_map/agreements-map"

        return f"[{summary}]({url})"

    def get_map_data(self, filters: dict) -> dict:
        """Return JSON data for the agreements map. Called by the web server endpoint."""
        results = self._execute_search(filters)

        by_country: dict[str, list[dict]] = {}
        for r in results:
            c = r["destination_country"]
            by_country.setdefault(c, []).append(r)

        # Large countries need lower zoom
        LARGE_COUNTRIES = {
            "Argentina": 4, "Australia": 4, "Brasil": 4, "Canadá": 4,
            "Chile": 4, "Colombia": 5, "Estados Unidos": 4, "India": 5,
            "Indonesia": 4, "Japón": 5, "Kazajistán": 4, "México": 5,
            "Perú": 5, "Sudáfrica": 5, "Turquía": 5,
        }

        # Determine map view
        view = CONTINENT_VIEW["world"]
        if filters.get("country"):
            for c in by_country:
                if c in COUNTRY_COORDS:
                    zoom = LARGE_COUNTRIES.get(c, 6)
                    view = {"center": COUNTRY_COORDS[c], "zoom": zoom}
                    break
        elif filters.get("continent"):
            continent = CONTINENT_ALIASES.get(
                filters["continent"].lower(), filters["continent"]
            )
            view = CONTINENT_VIEW.get(continent, CONTINENT_VIEW["world"])

        # Always return university-level markers — markercluster handles aggregation
        if self._uni_coords:
            markers = self._build_university_markers(results)
        else:
            markers = self._build_country_markers(by_country)

        has_geo_filter = bool(filters.get("continent") or filters.get("country") or filters.get("uninovis"))

        # UNINOVIS partners are in Europe
        if filters.get("uninovis") and not filters.get("continent") and not filters.get("country"):
            view = CONTINENT_VIEW["Europa"]

        return {
            "markers": markers,
            "center": view["center"],
            "zoom": view["zoom"],
            "has_geo_filter": has_geo_filter,
        }

    def _build_country_markers(self, by_country: dict) -> list:
        """Build country-level markers (for broad searches)."""
        markers = []
        for country, agreements in by_country.items():
            coords = COUNTRY_COORDS.get(country)
            if not coords:
                continue
            count = len(agreements)
            by_uni: dict[str, list[dict]] = {}
            for a in agreements:
                by_uni.setdefault(a["host_institution"], []).append(a)
            uni_lines = []
            for uni, uni_agr in sorted(by_uni.items()):
                fac_str = f" ({len(uni_agr)} agr.)" if len(uni_agr) > 1 else ""
                uni_lines.append(f"<b>{_display_name(uni)}</b>{fac_str}")
            popup = (
                f"<b>{country}</b> &mdash; {count} agreement{'s' if count != 1 else ''}<br>"
                f"<div style='max-height:200px;overflow-y:auto;margin-top:4px;font-size:12px;'>"
                + "<br>".join(uni_lines[:20])
                + (f"<br><i>... and {len(uni_lines)-20} more</i>" if len(uni_lines) > 20 else "")
                + "</div>"
            )
            markers.append({
                "lat": coords[0], "lon": coords[1],
                "count": count, "country": country, "popup": popup,
            })
        return markers

    def _build_university_markers(self, results: list[dict]) -> list:
        """Build university-level markers (for single-country or few-country searches)."""
        by_uni: dict[str, list[dict]] = {}
        for r in results:
            by_uni.setdefault(r["host_institution"], []).append(r)

        markers = []
        for uni, agreements in by_uni.items():
            uni_data = self._uni_coords.get(uni, {})
            lat = uni_data.get("lat")
            lon = uni_data.get("lon")
            if not lat or not lon:
                # Fallback to country center with small offset
                country = agreements[0]["destination_country"]
                country_coords = COUNTRY_COORDS.get(country)
                if not country_coords:
                    continue
                import random
                random.seed(hash(uni))
                lat = country_coords[0] + random.uniform(-1.5, 1.5)
                lon = country_coords[1] + random.uniform(-1.5, 1.5)

            count = len(agreements)
            # Build popup with expandable agreement details
            # Build popup HTML and also a data key for the "open in new window" feature
            data_key = f"algoria_uni_{abs(hash(uni))}"
            popup = (
                f"<div style='min-width:320px;'>"
                f"<b style='font-size:13px;'>{_display_name(uni)}</b><br>"
                f"<span style='color:#64748b;'>{agreements[0]['destination_country']}</span> "
                f"&mdash; {count} agreement{'s' if count != 1 else ''}"
                f"<div style='margin:6px 0;'>"
                f"<button onclick=\"window._algoriaOpenDetail('{data_key}')\" "
                f"style='background:#2563eb;color:#fff;border:none;border-radius:4px;"
                f"padding:4px 10px;font-size:11px;cursor:pointer;'>Open in new window</button>"
                f"</div>"
                f"<div style='max-height:300px;overflow-y:auto;'>"
            )
            detail_rows = []
            for j, a in enumerate(agreements):
                agr_id = f"popup-agr-{abs(hash(uni))}-{j}"
                prog = a.get("mobility_program") or ""
                # Show degrees instead of language
                degrees_desc = self._summarize_degrees(a)
                detail_html = self._format_agreement_detail(a)
                detail_rows.append(detail_html)
                popup += (
                    f"<div style='border-top:1px solid #e2e8f0;padding:4px 0;'>"
                    f"<div style='cursor:pointer;font-size:11px;' "
                    f"onclick=\"var d=document.getElementById('{agr_id}');"
                    f"d.style.display=d.style.display==='none'?'block':'none';\">"
                    f"<span style='color:#2563eb;'>&#9660;</span> "
                    f"<b>{prog}</b>"
                    f"{f' — {degrees_desc}' if degrees_desc else ''}"
                    f"</div>"
                    f"<div id='{agr_id}' style='display:none;font-size:11px;padding:4px 0 4px 12px;'>"
                    f"{detail_html}"
                    f"</div></div>"
                )
            popup += "</div></div>"

            # Store full detail HTML for the "open in new window" feature
            full_detail = "".join(
                f"<div style='border-bottom:1px solid #e2e8f0;padding:10px 0;'>"
                f"<b>Agreement {j+1}</b><br>{d}</div>"
                for j, d in enumerate(detail_rows)
            )
            markers.append({
                "lat": lat, "lon": lon,
                "count": count, "country": agreements[0]["destination_country"],
                "university": uni, "popup": popup,
                "detail_key": data_key,
                "detail_title": f"{_display_name(uni)} — {agreements[0]['destination_country']}",
                "detail_html": full_detail,
            })
        return markers

    def _describe_filters(self, filters: dict) -> str:
        """Build a human-readable description of the active filters."""
        parts = []
        if filters.get("continent"):
            parts.append(f"Continent: {filters['continent']}")
        if filters.get("country"):
            parts.append(f"Country: {filters['country']}")
        if filters.get("faculty"):
            parts.append(f"Faculty: {filters['faculty']}")
        if filters.get("language"):
            lang = filters["language"]
            if filters.get("language_level"):
                lang += f" {filters['language_level']}"
            parts.append(f"Language: {lang}")
        elif filters.get("language_level"):
            parts.append(f"Level: {filters['language_level']}")
        if filters.get("mobility_program"):
            parts.append(f"Program: {filters['mobility_program']}")
        if filters.get("degree_level"):
            parts.append(f"Degree: {filters['degree_level']}")
        if filters.get("university"):
            parts.append(f"University: {filters['university']}")
        return ", ".join(parts)

    def _build_list_html(self, results: list[dict]) -> str:
        """Build an HTML list with expandable agreement details."""
        if not results:
            return "<p>No agreements found matching your criteria.</p>"

        th = 'style="padding:5px 8px;text-align:left;border-bottom:2px solid #e2e8f0;"'
        td = 'style="padding:5px 8px;vertical-align:top;"'
        html = f'<table style="width:100%;border-collapse:collapse;font-size:0.85em;margin-top:8px;">'
        t = self._tr
        html += (f'<tr style="background:#f1f5f9;">'
                 f'<th {th}>{t("country", "Country")}</th>'
                 f'<th {th}>{t("university", "University")}</th>'
                 f'<th {th}>{t("degree_levels", "Degrees")}</th>'
                 f'<th {th}>{t("programs", "Program")}</th>'
                 f'<th {th}></th></tr>')

        for i, r in enumerate(results):
            degrees_desc = self._summarize_degrees(r)
            row_id = f"agr-detail-{i}"

            # Summary row
            html += (
                f'<tr style="border-bottom:1px solid #e2e8f0;cursor:pointer;" '
                f'onclick="var d=document.getElementById(\'{row_id}\');d.style.display=d.style.display===\'none\'?\'table-row\':\'none\';">'
                f'<td {td}>{r["destination_country"]}</td>'
                f'<td {td}>{_display_name(r["host_institution"])}</td>'
                f'<td {td}>{degrees_desc}</td>'
                f'<td {td}>{r["mobility_program"]}</td>'
                f'<td {td} style="padding:5px 4px;color:#2563eb;">&#9660;</td>'
                f'</tr>'
            )

            # Detail row (hidden by default)
            detail = self._format_agreement_detail(r)
            html += (
                f'<tr id="{row_id}" style="display:none;background:#f8fafc;">'
                f'<td colspan="5" style="padding:8px 12px;border-bottom:2px solid #e2e8f0;">{detail}</td>'
                f'</tr>'
            )

        html += '</table>'
        return html

    def _summarize_degrees(self, a: dict) -> str:
        """Summarize UMA faculties for an agreement row."""
        uma_fac = a.get("uma_faculties") or ""
        if not uma_fac or uma_fac == "Cualquier centro":
            return "Cualquier titulación"
        faculties = [f.strip() for f in uma_fac.split(" | ") if f.strip()]
        n = len(faculties)
        if n >= 18:
            return "Todas las facultades"
        if n >= 4:
            return "Varias facultades"
        # 1-3 faculties: show shortened names
        short = []
        for f in faculties:
            f = f.replace("Facultad de ", "").replace("Escuela Técnica Superior de ", "ETS ")
            f = f.replace("Escuela de ", "").replace("Servicio de ", "")
            short.append(f)
        return ", ".join(short)

    def _tr(self, key: str, fallback: str = "") -> str:
        """Get translation for key."""
        return self._t.get(key, fallback or key)

    def _format_agreement_detail(self, r: dict) -> str:
        """Format full details of a single agreement."""
        t = self._tr
        lines = []

        # Website
        uni = r.get("host_institution", "")
        website = self._uni_websites.get(uni)
        if website:
            lines.append(f"<b>{t('website', 'Web')}:</b> <a href='{website}' target='_blank' style='color:#2563eb;'>{website}</a>")

        # Validity
        start = r.get("start_date") or "—"
        end = r.get("end_date") or "—"
        lines.append(f"<b>{t('validity', 'Validity')}:</b> {start} — {end}")

        # Agreement ID
        if r.get("agreement_id"):
            lines.append(f"<b>{t('agreement_id', 'Agreement ID')}:</b> {r['agreement_id']}")

        # Host faculty
        if r.get("destination_faculty"):
            lines.append(f"<b>{t('host_faculty', 'Host faculty')}:</b> {r['destination_faculty']}")

        # UMA faculties
        if r.get("uma_faculties"):
            facs = r["uma_faculties"].replace(" | ", ", ")
            lines.append(f"<b>{t('uma_faculties', 'UMA faculties')}:</b> {facs}")

        # UMA degrees
        if r.get("uma_degrees") and r["uma_degrees"] != "Cualquier titulación":
            lines.append(f"<b>{t('uma_degrees', 'UMA degrees')}:</b> {r['uma_degrees']}")

        # Degree levels
        levels = []
        if r.get("allows_undergraduate") == "Sí":
            levels.append(t("undergraduate", "Undergraduate"))
        if r.get("allows_master") == "Sí":
            levels.append(t("master", "Master"))
        if r.get("allows_phd") == "Sí":
            levels.append(t("phd", "PhD"))
        if levels:
            lines.append(f"<b>{t('degree_levels', 'Degree levels')}:</b> {', '.join(levels)}")

        # Language 1
        if r.get("lang_1_name"):
            lang1 = f"{r['lang_1_name']} {r.get('lang_1_level', '')}".strip()
            cert = ""
            if r.get("lang_1_cert_mandatory") == "Sí":
                cert = f" ({t('cert_required', 'certificate required')}"
                if r.get("lang_1_cert_details"):
                    cert += f": {r['lang_1_cert_details']}"
                cert += ")"
            elif r.get("lang_1_cert_mandatory") == "No":
                cert = f" ({t('cert_not_required', 'no certificate required')})"
            lines.append(f"<b>{t('language_1', 'Language 1')}:</b> {lang1}{cert}")

        # Language 2
        if r.get("lang_2_name"):
            lang2 = f"{r['lang_2_name']} {r.get('lang_2_level', '')}".strip()
            cert = ""
            if r.get("lang_2_cert_mandatory") == "Sí":
                cert = f" ({t('cert_required', 'certificate required')}"
                if r.get("lang_2_cert_details"):
                    cert += f": {r['lang_2_cert_details']}"
                cert += ")"
            lines.append(f"<b>{t('language_2', 'Language 2')}:</b> {lang2}{cert}")

        # GPA
        if r.get("min_gpa_requirement") and r["min_gpa_requirement"] > 0:
            lines.append(f"<b>{t('min_gpa', 'Min. GPA')}:</b> {r['min_gpa_requirement']}")

        # Vacancies
        if r.get("student_vacancies"):
            lines.append(f"<b>{t('vacancies', 'Vacancies')}:</b> {r['student_vacancies']}")

        # Tutors
        if r.get("tutors"):
            tutors = r["tutors"]
            if len(tutors) > 200:
                tutor_list = tutors.split(" | ")
                tutors = ", ".join(tutor_list[:3])
                if len(tutor_list) > 3:
                    tutors += f" (+{len(tutor_list)-3} more)"
            lines.append(f"<b>{t('tutors', 'Tutors')}:</b> {tutors}")

        # Comments
        if r.get("public_comments") and r["public_comments"] not in ("Ninguno", ""):
            comment = r["public_comments"]
            if len(comment) > 300:
                comment = comment[:300] + "..."
            lines.append(f"<b>{t('comments', 'Comments')}:</b> {comment}")

        return "<br>".join(lines)

    # ------------------------------------------------------------------
    # Chat interface (called by web server)
    # ------------------------------------------------------------------

    def chat(self, user_message: str, history: list = None, **kwargs) -> str:
        model = kwargs.get("model_override") or self.model

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Call LLM with tools
        response = self.client.chat.complete(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="any",
        )

        choice = response.choices[0]

        # Check for tool calls
        if choice.message.tool_calls:
            tc = choice.message.tool_calls[0]
            func_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}

            if func_name == "search_agreements":
                return self._handle_search(args)

        # Fallback: no tool call — LLM responded directly
        content = choice.message.content or ""
        if content:
            return content
        return "I can help you explore UMA mobility agreements. Try asking something like: *Show agreements in Italy* or *Show all agreements*."

    async def chat_stream(self, user_message: str, history: list = None, **kwargs):
        """Streaming version — yields (event_type, content) tuples."""
        yield ("status", "Searching agreements...")

        try:
            model = kwargs.get("model_override") or self.model

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            response = self.client.chat.complete(
                model=model, messages=messages, tools=TOOLS, tool_choice="any",
            )
            choice = response.choices[0]

            if choice.message.tool_calls:
                tc = choice.message.tool_calls[0]
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                if tc.function.name == "search_agreements":
                    results = self._execute_search(args)
                    if not results:
                        yield ("content", "No agreements found matching your criteria. Try a broader search.")
                        return
                    by_country = {}
                    for r in results:
                        by_country[r["destination_country"]] = by_country.get(r["destination_country"], 0) + 1
                    # Send map as markdown link (frontend intercepts and renders Leaflet map)
                    map_link = self._build_map_link(args, len(results), len(by_country))
                    yield ("content", map_link + "\n\n")
                    # Send list or summary
                    if len(results) <= 30:
                        yield ("content", self._build_list_html(results))
                    else:
                        yield ("content",
                               f"Showing {len(results)} agreements across {len(by_country)} countries. "
                               "Try narrowing your search (e.g. by country, faculty, or language) to see details.")
                    return

            content = choice.message.content or ""
            yield ("content", content or "Try asking something like: *Show agreements in Italy*")
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield ("content", f"Error processing your request: {str(e)}")

    def _handle_search(self, filters: dict) -> str:
        """Execute search and build map + optional list."""
        results = self._execute_search(filters)

        if not results:
            return "No agreements found matching your criteria. Try a broader search."

        by_country: dict[str, int] = {}
        for r in results:
            by_country[r["destination_country"]] = by_country.get(r["destination_country"], 0) + 1

        # Map link + list or summary
        html = self._build_map_link(filters, len(results), len(by_country)) + "\n\n"

        if len(results) <= 30:
            html += self._build_list_html(results)
        else:
            # Show count per country summary
            by_country: dict[str, int] = {}
            for r in results:
                c = r["destination_country"]
                by_country[c] = by_country.get(c, 0) + 1
            html += '<div style="margin-top:8px;font-size:0.85em;color:#64748b;">'
            html += f'Showing {len(results)} agreements across {len(by_country)} countries. '
            html += 'Try narrowing your search (e.g. by country, faculty, or language) to see details.'
            html += '</div>'

        self._query_history.append({
            "question": filters,
            "result_count": len(results),
        })

        return html

    # ------------------------------------------------------------------
    # Required interface methods
    # ------------------------------------------------------------------

    def get_schema(self):
        schema_path = os.path.join(self._agent_dir, "data", "destinations.md")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""
