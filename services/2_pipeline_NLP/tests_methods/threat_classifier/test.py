import re
import unicodedata
from typing import Dict, Optional, TypedDict, Literal
ThreatLevel = Literal["critical", "high", "medium", "low", "info"]
ThreatSource = Literal["keyword"]
EventCategory = Literal[
    "military",
    "conflict",
    "terrorism",
    "health",
    "disaster",
    "crime",
    "cyber",
    "economic",
    "protest",
    "diplomatic",
    "environmental",
    "infrastructure",
    "tech",
    "general",
]
class ThreatClassification(TypedDict):
    level: ThreatLevel
    category: EventCategory
    confidence: float
    source: ThreatSource
KeywordMap = Dict[str, EventCategory]
CRITICAL_KEYWORDS: KeywordMap = {
    "ataque nuclear": "military",
    "golpe nuclear": "military",
    "guerra nuclear": "military",
    "invasion": "conflict",
    "declaracion de guerra": "conflict",
    "declara la guerra": "conflict",
    "guerra total": "conflict",
    "guerra a gran escala": "conflict",
    "ley marcial": "military",
    "golpe de estado": "military",
    "intento de golpe": "military",
    "genocidio": "conflict",
    "limpieza etnica": "conflict",
    "ataque quimico": "terrorism",
    "ataque biologico": "terrorism",
    "bomba sucia": "terrorism",
    "muchas victimas": "conflict",
    "ataques masivos": "military",
    "ataques militares": "military",
    "ataques de represalia": "military",
    "lanza ataques": "military",
    "ataque a iran": "military",
    "ataques a iran": "military",
    "bombardeo a iran": "military",
    "bombardea iran": "military",
    "ataca iran": "military",
    "guerra con iran": "conflict",
    "guerra contra iran": "conflict",
    "iran responde": "military",
    "iran ataca": "military",
    "iran lanza": "military",
    "pandemia declarada": "health",
    "emergencia sanitaria": "health",
    "articulo 5 de la otan": "military",
    "orden de evacuacion": "disaster",
    "fusion del nucleo": "disaster",
    "fusion nuclear": "disaster",
    "operaciones de combate mayores": "military",
}
HIGH_KEYWORDS: KeywordMap = {
    "guerra": "conflict",
    "conflicto armado": "conflict",
    "ataque aereo": "conflict",
    "ataques aereos": "conflict",
    "ataque con drones": "conflict",
    "ataques con drones": "conflict",
    "misil": "military",
    "lanzamiento de misil": "military",
    "misiles disparados": "military",
    "despliegue de tropas": "military",
    "escalada militar": "military",
    "operacion militar": "military",
    "ofensiva terrestre": "military",
    "bombardeo": "conflict",
    "bombardeos": "conflict",
    "bombardeamiento": "conflict",
    "cañoneo": "conflict",
    "victimas": "conflict",
    "muertos en": "conflict",
    "rehen": "terrorism",
    "rehenes": "terrorism",
    "terrorista": "terrorism",
    "ataque terrorista": "terrorism",
    "asesinato": "crime",
    "ciberataque": "cyber",
    "ataque cibernetico": "cyber",
    "ransomware": "cyber",
    "filtracion de datos": "cyber",
    "sanciones": "economic",
    "embargo": "economic",
    "terremoto": "disaster",
    "tsunami": "disaster",
    "huracan": "disaster",
    "tifon": "disaster",
    "ataque contra": "conflict",
    "ataques contra": "conflict",
    "explosiones": "conflict",
    "operaciones militares": "military",
    "operaciones de combate": "military",
    "ataque de represalia": "military",
    "ataques de represalia": "military",
    "ataque preventivo": "military",
    "ofensiva militar": "military",
    "misil balistico": "military",
    "misil de crucero": "military",
    "defensa aerea intercepto": "military",
}
MEDIUM_KEYWORDS: KeywordMap = {
    "protesta": "protest",
    "protestas": "protest",
    "disturbio": "protest",
    "disturbios": "protest",
    "agitacion": "protest",
    "manifestacion": "protest",
    "huelga": "protest",
    "ejercicio militar": "military",
    "ejercicio naval": "military",
    "acuerdo de armas": "military",
    "venta de armas": "military",
    "crisis diplomatica": "diplomatic",
    "retiro del embajador": "diplomatic",
    "expulsa diplomaticos": "diplomatic",
    "guerra comercial": "economic",
    "arancel": "economic",
    "recesion": "economic",
    "inflacion": "economic",
    "caida del mercado": "economic",
    "inundacion": "disaster",
    "inundaciones": "disaster",
    "incendio forestal": "disaster",
    "volcan": "disaster",
    "erupcion": "disaster",
    "brote": "health",
    "epidemia": "health",
    "propagacion de infeccion": "health",
    "derrame de petroleo": "environmental",
    "explosion de oleoducto": "infrastructure",
    "apagon": "infrastructure",
    "corte de energia": "infrastructure",
    "caida de internet": "infrastructure",
    "descarrilamiento": "infrastructure",
}
LOW_KEYWORDS: KeywordMap = {
    "eleccion": "diplomatic",
    "elecciones": "diplomatic",
    "voto": "diplomatic",
    "referendum": "diplomatic",
    "cumbre": "diplomatic",
    "tratado": "diplomatic",
    "acuerdo": "diplomatic",
    "negociacion": "diplomatic",
    "negociaciones": "diplomatic",
    "dialogo": "diplomatic",
    "conversaciones": "diplomatic",
    "mantenimiento de la paz": "diplomatic",
    "ayuda humanitaria": "diplomatic",
    "alto el fuego": "diplomatic",
    "tratado de paz": "diplomatic",
    "cambio climatico": "environmental",
    "emisiones": "environmental",
    "contaminacion": "environmental",
    "deforestacion": "environmental",
    "sequia": "environmental",
    "vacuna": "health",
    "vacunacion": "health",
    "enfermedad": "health",
    "virus": "health",
    "salud publica": "health",
    "covid": "health",
    "tasa de interes": "economic",
    "pib": "economic",
    "desempleo": "economic",
    "regulacion": "economic",
}
TECH_HIGH_KEYWORDS: KeywordMap = {
    "caida masiva": "infrastructure",
    "servicio caido": "infrastructure",
    "caida global": "infrastructure",
    "zero day": "cyber",
    "vulnerabilidad critica": "cyber",
    "ataque a la cadena de suministro": "cyber",
    "despido masivo": "economic",
}
TECH_MEDIUM_KEYWORDS: KeywordMap = {
    "caida del servicio": "infrastructure",
    "brecha": "cyber",
    "hackeo": "cyber",
    "vulnerabilidad": "cyber",
    "despido": "economic",
    "despidos": "economic",
    "antimonopolio": "economic",
    "monopolio": "economic",
    "bloqueo": "economic",
    "cierre": "infrastructure",
}
TECH_LOW_KEYWORDS: KeywordMap = {
    "ipo": "economic",
    "financiacion": "economic",
    "adquisicion": "economic",
    "fusion": "economic",
    "lanzamiento": "tech",
    "publicacion": "tech",
    "actualizacion": "tech",
    "alianza": "economic",
    "startup": "tech",
    "modelo de ia": "tech",
    "codigo abierto": "tech",
}
EXCLUSIONS = [
    "proteina",
    "parejas",
    "relacion",
    "citas",
    "dieta",
    "fitness",
    "receta",
    "cocina",
    "compras",
    "moda",
    "celebridad",
    "pelicula",
    "serie",
    "deportes",
    "juego",
    "concierto",
    "festival",
    "boda",
    "vacaciones",
    "consejos de viaje",
    "bienestar",
]
SHORT_KEYWORDS = {
    "guerra",
    "voto",
    "hackeo",
    "ipo",
    "pib",
    "virus",
    "brote",
}
ESCALATION_ACTIONS = re.compile(
    r"\b("
    r"ataque|ataques|ataco|atacan|atacaron|bombardeo|bombardeos|bombardear|"
    r"misil|misiles|intercepto|interceptados|represalia|ofensiva|invasion|"
    r"invadio|invaden|muertos|victimas"
    r")\b"
)
ESCALATION_TARGETS = re.compile(
    r"\b("
    r"iran|teheran|isfahan|tabriz|rusia|moscu|china|beijing|taiwan|taipei|"
    r"corea del norte|pyongyang|otan|base estadounidense|fuerzas estadounidenses|"
    r"ejercito estadounidense"
    r")\b"
)
def normalize_text(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    return text
def get_keyword_regex(keyword: str) -> re.Pattern[str]:
    escaped = re.escape(keyword)
    if keyword in SHORT_KEYWORDS:
        return re.compile(rf"\b{escaped}\b")
    return re.compile(escaped)
def match_keywords(text: str, keywords: KeywordMap) -> Optional[dict]:
    for kw, category in keywords.items():
        if get_keyword_regex(kw).search(text):
            return {"keyword": kw, "category": category}
    return None
def should_escalate_to_critical(text: str, category: EventCategory) -> bool:
    if category not in ("conflict", "military"):
        return False
    return bool(ESCALATION_ACTIONS.search(text) and ESCALATION_TARGETS.search(text))
def classify_news(text: str, variant: str = "full") -> ThreatClassification:
    lower = normalize_text(text)
    if any(ex in lower for ex in EXCLUSIONS):
        return {
            "level": "info",
            "category": "general",
            "confidence": 0.3,
            "source": "keyword",
        }
    is_tech = variant == "tech"
    match = match_keywords(lower, CRITICAL_KEYWORDS)
    if match:
        return {
            "level": "critical",
            "category": match["category"],
            "confidence": 0.9,
            "source": "keyword",
        }
    match = match_keywords(lower, HIGH_KEYWORDS)
    if match:
        if should_escalate_to_critical(lower, match["category"]):
            return {
                "level": "critical",
                "category": match["category"],
                "confidence": 0.85,
                "source": "keyword",
            }
        return {
            "level": "high",
            "category": match["category"],
            "confidence": 0.8,
            "source": "keyword",
        }
    if is_tech:
        match = match_keywords(lower, TECH_HIGH_KEYWORDS)
        if match:
            return {
                "level": "high",
                "category": match["category"],
                "confidence": 0.75,
                "source": "keyword",
            }
    match = match_keywords(lower, MEDIUM_KEYWORDS)
    if match:
        return {
            "level": "medium",
            "category": match["category"],
            "confidence": 0.7,
            "source": "keyword",
        }
    if is_tech:
        match = match_keywords(lower, TECH_MEDIUM_KEYWORDS)
        if match:
            return {
                "level": "medium",
                "category": match["category"],
                "confidence": 0.65,
                "source": "keyword",
            }
    match = match_keywords(lower, LOW_KEYWORDS)
    if match:
        return {
            "level": "low",
            "category": match["category"],
            "confidence": 0.6,
            "source": "keyword",
        }
    if is_tech:
        match = match_keywords(lower, TECH_LOW_KEYWORDS)
        if match:
            return {
                "level": "low",
                "category": match["category"],
                "confidence": 0.55,
                "source": "keyword",
            }
    return {
        "level": "info",
        "category": "general",
        "confidence": 0.3,
        "source": "keyword",
    }
if __name__ == "__main__":
    noticia = "La zona Quién es el problema en esta zona Para según Estados Unidos es irán que agita la estabilidad de la región Por lo tanto estos dos objetivos meco objetivo Digamos están pendientes de ser realizados Pero luego están Israel El problema de Israel es más grave con Irán Porque ellos lo que quieren es primero llevar a Irán a la edad media Que es lo que están haciendo en realidad Han destruido buena parte de la industria iraní Han golpeado hasta las regeneras Ya no digamos las centrales nucleares Y han llevado prácticamente irán a la una pobreza extrema Que de aquí décadas no levantará la cabeza en el mejor de los casos de las situaciones Y segundo quiere acabar con el régimen islámico Esto es so objetivo Entonces hasta que no consiga esto esta guerra continuará Yo lo que quiere creo es que como el régimen de Irán Que ahora estaba con control de los militares Porque hay un dato muy interesante que ha ocurrido por esta guerra Que el que le digo ha sido eliminado del poder de la teocracia islámica No están ya no veremos a ver a los hombres de Sotana En el poder Algunos pasarán por ahí por para decir que aquí estamos Pero el poder real estaba bajo el control de los militares En hecho como un denegó al prestado Incluso han apartado al presidente de la República Islámica Que es pes esquían la han apartado prácticamente en la fan desautorizado"
    resultado = classify_news(noticia, variant="full")
    print("Clasificacion:")
    print(resultado)