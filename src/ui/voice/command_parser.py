import re
from dataclasses import dataclass
from typing import Optional

from src.ui.controller_config import ControllerAction


@dataclass
class TimedMove:
    """Describes a timed movement command."""
    x: float = 0.0       # forward/backward speed
    y: float = 0.0       # left/right strafe speed
    z: float = 0.0       # rotation speed
    duration: float = 1.0  # seconds


@dataclass
class ParsedCommand:
    """Result of parsing a voice command."""
    action: Optional[ControllerAction] = None
    timed_move: Optional[TimedMove] = None
    is_stop: bool = False
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Multi-language action keywords  (longer phrases first to avoid partial hits)
# ---------------------------------------------------------------------------
_ACTION_KEYWORDS: list[tuple[list[str], ControllerAction]] = [
    # SIT
    ([
        # en – base + colloquial / Whisper variants
        "sit down", "sit", "take a seat", "sitting",
        # pl – formal, informal, imperative, no-diacritics
        "siądź", "siadaj", "siad", "usiądź", "siadaj się",
        "siadz", "usiadz",                            # no-diacritics whisper
        "shad", "shiad", "shiadz", "shadj",           # Whisper phonetic mishearing pl→en
        # de
        "setz dich", "hinsetzen", "sitz", "setz dich hin", "sitzen",
        # es
        "siéntate", "sentarse", "sentate", "sientate",
        # fr
        "assieds-toi", "assis", "assied toi", "assieds toi",
        # it
        "siediti", "seduto", "siediti giù",
        # pt
        "senta", "sente", "senta-se",
        # ja
        "おすわり", "座って", "座れ", "すわって", "すわれ",
        # zh
        "坐下", "坐",
        # ko
        "앉아라", "앉아", "앉기",
        # ru
        "сядь", "сесть", "сидеть", "садись", "присядь",
        # uk
        "сідай", "сядь", "сідати",
        # nl
        "ga zitten", "zit", "zitten",
        # sv
        "sätt dig", "sitt", "sitta", "sätt dig ner",
        # cs – with and without háčky
        "sedni si", "sedni", "sedněte", "sedni si", "sedni",
        # tr
        "otur", "oturun",
    ], ControllerAction.SIT),

    # STAND UP
    ([
        # en
        "stand up", "stand", "get up", "rise", "on your feet",
        # pl
        "wstań", "wstawaj", "wstawaj się", "powstań",
        "wstan", "wstawaj",                            # no-diacritics
        "fstan", "vstan", "vstanj",                    # Whisper phonetic mishearing
        # de
        "steh auf", "aufstehen", "steh", "hoch",
        # es
        "levántate", "párate", "levantate", "parate", "arriba",
        # fr
        "lève-toi", "debout", "leve-toi", "leve toi", "levez-vous",
        # it
        "alzati", "in piedi", "alzarsi", "su",
        # pt
        "levanta", "levante", "levanta-se", "em pé",
        # ja
        "立って", "立て", "起きて", "たって", "たて",
        # zh
        "站起来", "起立", "站起",
        # ko
        "일어나", "일어서", "일어서기",
        # ru
        "встань", "встать", "вставай", "поднимись",
        # uk
        "встань", "вставай", "підведись", "піднімись",
        # nl
        "sta op", "opstaan", "overeind",
        # sv
        "res dig", "ställ dig upp", "res dig upp", "upp",
        # cs
        "vstaň", "vstát", "vstan", "vstat",           # no-diacritics
        # tr
        "ayağa kalk", "kalk", "kalkın",
    ], ControllerAction.STAND_UP),

    # STAND DOWN / LIE DOWN
    ([
        # en
        "stand down", "lie down", "lay down", "down", "lie",
        # pl
        "połóż się", "leżeć", "leż", "kładź się", "padnij",
        "poloz sie", "lezec", "lez",                   # no-diacritics
        "polosh shie", "leshech", "padniy",            # Whisper phonetic mishearing
        # de
        "leg dich hin", "hinlegen", "leg dich", "platz", "legen",
        # es
        "acuéstate", "échate", "acuestate", "echate", "abajo", "tumbarse",
        # fr
        "couche-toi", "allonge-toi", "couche toi", "allonge toi", "au sol",
        # it
        "sdraiati", "coricati", "a terra", "giù",
        # pt
        "deita", "deite", "deita-se", "deitar",
        # ja
        "伏せて", "伏せ", "ふせて", "ふせ",
        # zh
        "趴下", "躺下", "卧倒",
        # ko
        "엎드려", "누워", "엎드리기",
        # ru
        "ляг", "ложись", "лечь", "лёг", "ложиться",
        # uk
        "лягай", "ляж", "лягти", "ляг",
        # nl
        "ga liggen", "lig", "liggen", "neer",
        # sv
        "lägg dig", "ligg ner", "lägg dig ner", "ner",
        # cs
        "lehni si", "lehni", "lehni si", "poloz se",
        # tr
        "yat", "uzan", "yere yat",
    ], ControllerAction.STAND_DOWN),

    # STRETCH
    ([
        # en
        "stretch", "stretching",
        # pl
        "przeciągnij się", "rozciągnij się", "przeciagnij sie", "rozciagnij sie",
        "pshechiongniy shie", "rozchiongniy",          # Whisper phonetic mishearing
        # de
        "streck dich", "strecken", "streck", "dehnen",
        # es
        "estírate", "estirar", "estirate", "estiramiento",
        # fr
        "étire-toi", "étirement", "etire-toi", "etire toi", "etirement",
        # it
        "stiracchiati", "allungati", "allungamento",
        # pt
        "alongar", "esticar", "alongamento",
        # ja
        "ストレッチ", "伸び", "のび",
        # zh
        "伸展", "拉伸", "伸懒腰",
        # ko
        "스트레칭", "기지개",
        # ru
        "потянись", "растяжка", "потянуться", "растянись",
        # uk
        "потягнись", "розтяжка", "потягнися",
        # nl
        "rek uit", "stretch", "rekken", "strekken",
        # sv
        "sträck", "stretcha", "sträck dig", "sträck på dig",
        # cs
        "protáhni se", "protažení", "protahni se", "protazeni",
        # tr
        "gerin", "esne", "gerinme", "esneme",
    ], ControllerAction.STRETCH),

    # HELLO / WAVE
    ([
        # en
        "hello", "wave", "hi", "hey", "greet", "howdy", "yo",
        # pl
        "cześć", "hej", "witaj", "pomachaj", "siema", "elo",
        "czesc", "pomachaj",                           # no-diacritics
        "cheshch", "vitay", "pomahay",                 # Whisper phonetic mishearing
        # de
        "hallo", "winken", "grüß", "servus", "moin", "wink",
        # es
        "hola", "saluda", "saludar", "buenos días", "buenos dias",
        # fr
        "bonjour", "salut", "coucou", "bonsoir",
        # it
        "ciao", "saluta", "salutare", "buongiorno",
        # pt
        "olá", "oi", "acena", "ola", "acenar", "e aí",
        # ja
        "こんにちは", "ハロー", "おーい", "やあ",
        # zh
        "你好", "挥手", "嗨", "哈喽",
        # ko
        "안녕", "인사", "안녕하세요",
        # ru
        "привет", "помаши", "здравствуй", "здарова", "махни",
        # uk
        "привіт", "помахай", "здоровенькі", "махни",
        # nl
        "hallo", "hoi", "zwaai", "zwaaien", "dag",
        # sv
        "hej", "hejsan", "vinka", "hallå", "tjena",
        # cs
        "ahoj", "čau", "zamávej", "cau", "zamavej",   # no-diacritics
        # tr
        "merhaba", "selam", "el salla",
    ], ControllerAction.HELLO),

    # JUMP
    ([
        # en
        "jump", "hop", "leap", "bounce",
        # pl
        "skacz", "skok", "skocz", "podskocz",
        "skach", "skoch", "skots",                     # Whisper phonetic mishearing
        # de
        "spring", "sprung", "springen", "hüpfen", "hüpf", "huepfen",
        # es
        "salta", "saltar", "brincar", "brinca",
        # fr
        "saute", "sauter", "bondir", "bondis",
        # it
        "salta", "saltare", "balza",
        # pt
        "pula", "pular", "salta",
        # ja
        "ジャンプ", "跳べ", "跳んで", "とべ", "とんで",
        # zh
        "跳", "跳跃", "蹦",
        # ko
        "점프", "뛰어", "뛰기",
        # ru
        "прыгай", "прыжок", "прыгни", "скачи",
        # uk
        "стрибай", "стрибок", "стрибни",
        # nl
        "spring", "sprong", "springen",
        # sv
        "hoppa", "hopp",
        # cs
        "skoč", "skákej", "skoc", "skakej",           # no-diacritics
        # tr
        "zıpla", "atla", "zipla",                      # no-diacritics
    ], ControllerAction.JUMP),

    # DANCE
    ([
        # en
        "dance", "dancing", "boogie", "groove",
        # pl
        "tańcz", "taniec", "zatańcz", "tancz", "tanczyc",
        "tanch", "taniets", "zatanch",                 # Whisper phonetic mishearing
        # de
        "tanz", "tanzen", "tanze",
        # es
        "baila", "bailar", "bailemos",
        # fr
        "danse", "danser", "dansez",
        # it
        "balla", "ballare", "balli",
        # pt
        "dança", "dançar", "danca", "dancar",          # no-diacritics
        # ja
        "ダンス", "踊れ", "踊って", "おどれ", "おどって",
        # zh
        "跳舞", "舞蹈", "跳个舞",
        # ko
        "춤", "댄스", "춤춰", "춤을 춰",
        # ru
        "танцуй", "танец", "танцевать", "потанцуй",
        # uk
        "танцюй", "танець", "танцювати", "потанцюй",
        # nl
        "dans", "dansen",
        # sv
        "dansa", "dans",
        # cs
        "tancuj", "tanec", "tancovat",
        # tr
        "dans et", "oyna", "dans",
    ], ControllerAction.DANCE1),

    # FINGER HEART
    ([
        # en
        "finger heart", "heart", "love",
        # pl
        "serce", "serduszko",
        # de
        "finger herz", "herz",
        # es
        "corazón", "corazon",                          # no-diacritics
        # fr
        "coeur", "cœur",
        # it
        "cuore",
        # pt
        "coração", "coracao",                          # no-diacritics
        # ja
        "指ハート", "ハート",
        # zh
        "比心", "爱心",
        # ko
        "손가락 하트", "하트",
        # ru
        "сердце", "сердечко",
        # uk
        "серце", "серденько",
        # nl
        "hart", "hartje",
        # sv
        "hjärta", "hjarta",                            # no-diacritics
        # cs
        "srdce", "srdíčko", "srdicko",                # no-diacritics
        # tr
        "kalp",
    ], ControllerAction.FINGER_HEART),

    # TOGGLE FLASH
    ([
        # en
        "flashlight", "flash", "light", "torch", "lamp",
        # pl
        "latarka", "światło", "swiatlo",               # no-diacritics
        "shviatwo", "latarca",                         # Whisper phonetic mishearing
        # de
        "taschenlampe", "licht", "lampe",
        # es
        "linterna", "luz",
        # fr
        "lampe", "lumière", "lumiere", "torche",
        # it
        "torcia", "luce",
        # pt
        "lanterna", "luz",
        # ja
        "フラッシュ", "ライト", "懐中電灯",
        # zh
        "手电", "闪光灯", "灯",
        # ko
        "플래시", "손전등", "라이트",
        # ru
        "фонарик", "свет", "фонарь",
        # uk
        "ліхтарик", "світло", "ліхтар",
        # nl
        "zaklamp", "licht", "lamp",
        # sv
        "ficklampa", "ljus", "lampa",
        # cs
        "svítilna", "baterka", "světlo", "svitilna", "svetlo",
        # tr
        "el feneri", "fener", "ışık", "isik",          # no-diacritics
    ], ControllerAction.TOGGLE_FLASH),

    # TOGGLE LED
    ([
        # en
        "led", "color", "colour",
        # pl
        "kolor", "dioda",
        # de
        "farbe",
        # es
        "color",
        # fr
        "couleur",
        # it
        "colore",
        # pt
        "cor",
        # ja
        "カラー", "色",
        # zh
        "颜色",
        # ko
        "색상", "컬러",
        # ru
        "цвет", "светодиод",
        # uk
        "колір", "світлодіод", "колир",                # no-diacritics
        # nl
        "kleur",
        # sv
        "färg", "farg",                                # no-diacritics
        # cs
        "barva",
        # tr
        "renk",
    ], ControllerAction.TOGGLE_LED),

    # TOGGLE LIDAR
    ([
        "lidar",                                       # universal
        "лидар",                                       # ru/uk
        "라이다",                                       # ko
        "ライダー",                                     # ja
    ], ControllerAction.TOGGLE_LIDAR),
]

# ---------------------------------------------------------------------------
# Stop keywords (all languages)
# ---------------------------------------------------------------------------
_STOP_WORDS: set[str] = {
    # en
    "stop", "halt", "freeze", "enough", "cancel",
    # pl + no-diacritics + Whisper phonetic
    "stój", "zatrzymaj się", "stoj", "zatrzymaj sie", "koniec",
    "stooy", "stuy", "zatshimay shie",                 # Whisper phonetic
    # de
    "stopp", "anhalten", "stehen", "aus",
    # es
    "para", "alto", "detente", "basta",
    # fr
    "arrête", "arrêter", "arrete", "arreter",
    # it
    "ferma", "fermati", "basta", "fermo",
    # pt
    "pare", "parar", "chega",
    # ja
    "止まれ", "ストップ", "止まって", "とまれ", "とまって", "やめて",
    # zh
    "停", "停止", "站住", "别动",
    # ko
    "멈춰", "정지", "스톱", "그만",
    # ru
    "стоп", "стой", "остановись", "хватит",
    # uk
    "стоп", "стій", "зупинись", "стiй",               # no-diacritics
    # nl
    "stop", "sta stil", "stilstaan",
    # sv
    "stopp", "stanna", "stå still",
    # cs + no-diacritics
    "stůj", "zastavit", "stuj", "zastavit", "dost",
    # tr
    "dur", "durdurmak",
}

# ---------------------------------------------------------------------------
# Movement / rotation keyword tables
# ---------------------------------------------------------------------------

# Direction -> (x, y, z) mapping
_DIRECTION_FORWARD: set[str] = {
    # en
    "forward", "forwards", "ahead", "straight",
    # pl + no-diacritics + Whisper phonetic
    "do przodu", "naprzód", "przód", "naprzod", "przod", "prosto",
    "do pshodu", "napshod", "pshod",                   # Whisper phonetic
    # de
    "vorwärts", "vor", "vorwaerts", "geradeaus",
    # es
    "adelante", "al frente", "enfrente",
    # fr
    "en avant", "avant", "devant", "tout droit",
    # it
    "avanti", "dritto",
    # pt
    "frente", "em frente", "para frente",
    # ja
    "前", "前方", "前に", "まえ",
    # zh
    "前", "前方", "前进", "往前",
    # ko
    "앞으로", "앞",
    # ru
    "вперёд", "вперед", "прямо",
    # uk
    "вперед", "прямо",
    # nl
    "vooruit", "naar voren", "rechtdoor",
    # sv
    "framåt", "framat", "rakt fram",
    # cs + no-diacritics
    "vpřed", "dopředu", "vpred", "dopredu", "rovně", "rovne",
    # tr
    "ileri", "düz", "duz",
}

_DIRECTION_BACKWARD: set[str] = {
    # en
    "backward", "backwards", "back", "reverse",
    # pl + no-diacritics + Whisper phonetic
    "do tyłu", "tył", "w tył", "do tylu", "tyl", "w tyl", "cofnij",
    "do tywu", "tyw", "cofniy",                        # Whisper phonetic
    # de
    "rückwärts", "zurück", "rueckwaerts", "zurueck",
    # es
    "atrás", "atras", "hacia atrás", "hacia atras", "reversa",
    # fr
    "en arrière", "arrière", "en arriere", "arriere", "recule", "reculer",
    # it
    "indietro", "dietro",
    # pt
    "trás", "para trás", "tras", "para tras",
    # ja
    "後ろ", "後方", "後ろに", "うしろ",
    # zh
    "后", "后方", "后退", "往后",
    # ko
    "뒤로", "뒤",
    # ru/uk
    "назад",
    # nl
    "achteruit", "naar achteren", "terug",
    # sv
    "bakåt", "bakat", "tillbaka",
    # cs + no-diacritics
    "vzad", "dozadu", "zpět", "zpet",
    # tr
    "geri",
}

_DIRECTION_LEFT: set[str] = {
    # en
    "left",
    # pl
    "w lewo", "lewo", "na lewo",
    # de/nl
    "links",
    # es
    "izquierda", "a la izquierda",
    # fr
    "gauche", "à gauche", "a gauche",
    # it
    "sinistra", "a sinistra",
    # pt
    "esquerda", "à esquerda",
    # ja/zh
    "左", "ひだり",
    # ko
    "왼쪽",
    # ru
    "влево", "налево",
    # uk
    "вліво", "наліво",
    # sv
    "vänster", "vanster",
    # cs + no-diacritics
    "vlevo", "doleva",
    # tr
    "sol", "sola",
}

_DIRECTION_RIGHT: set[str] = {
    # en
    "right",
    # pl
    "w prawo", "prawo", "na prawo",
    # de/nl
    "rechts",
    # es
    "derecha", "a la derecha",
    # fr
    "droite", "à droite", "a droite",
    # it
    "destra", "a destra",
    # pt
    "direita", "à direita",
    # ja/zh
    "右", "みぎ",
    # ko
    "오른쪽",
    # ru
    "вправо", "направо",
    # uk
    "вправо", "направо",
    # sv
    "höger", "hoger",
    # cs + no-diacritics
    "vpravo", "doprava",
    # tr
    "sağ", "sağa", "sag", "saga",
}

# Movement verbs (triggers x/y movement)
_MOVE_VERBS: set[str] = {
    # en
    "move", "go", "walk", "step", "head",
    # pl + no-diacritics
    "idź", "jedź", "ruszaj", "idz", "jedz", "chodź", "chodz",
    # de
    "geh", "beweg dich", "lauf", "gehen", "laufen",
    # es
    "ve", "camina", "muévete", "avanza", "muevete", "anda",
    # fr
    "va", "marche", "avance", "bouge", "aller",
    # it
    "vai", "cammina", "muoviti", "muovi",
    # pt
    "vá", "ande", "mova", "va",
    # ja
    "進め", "歩け", "動け", "すすめ", "あるけ", "うごけ",
    # zh
    "走", "移动", "前进", "行走",
    # ko
    "가", "걸어", "이동",
    # ru
    "иди", "двигайся", "шагай", "ходи",
    # uk
    "іди", "рухайся", "ходи",
    # nl
    "ga", "loop", "beweeg", "stap",
    # sv
    "gå", "rör dig", "ga",
    # cs + no-diacritics
    "jdi", "pohni se", "chod",
    # tr
    "git", "yürü", "yuru",
}

# Fast movement verbs (speed = 1.0 instead of 0.5)
_RUN_VERBS: set[str] = {
    # en
    "run", "sprint", "fast", "quick",
    # pl + no-diacritics
    "biegnij", "biegaj", "pędź", "pedz", "szybko",
    # de
    "renn", "renne", "rennen", "schnell",
    # es
    "corre", "correr", "rápido", "rapido",
    # fr
    "cours", "courir", "vite",
    # it
    "corri", "correre", "veloce",
    # pt
    "corra", "correr", "rápido", "rapido",
    # ja
    "走れ", "走って", "はしれ", "はしって", "速く",
    # zh
    "跑", "快跑", "快",
    # ko
    "달려", "빨리",
    # ru
    "беги", "бегом", "быстро", "быстрей",
    # uk
    "біжи", "бігом", "швидко", "швидше",
    # nl
    "ren", "rennen", "snel",
    # sv
    "spring", "springa", "snabbt",
    # cs + no-diacritics
    "běž", "bez", "rychle",
    # tr
    "koş", "kos", "hızlı", "hizli",
}

# Rotation verbs (triggers z rotation)
_TURN_VERBS: set[str] = {
    # en
    "turn", "rotate", "spin", "twist",
    # pl + no-diacritics
    "obróć się", "skręć", "obroc sie", "skrec", "kręć", "krec", "obróć", "obroc",
    # de
    "dreh dich", "drehen", "dreh",
    # es
    "gira", "girar", "rota", "rotar",
    # fr
    "tourne", "tourner", "pivote", "pivoter",
    # it
    "gira", "ruota", "girare", "ruotare",
    # pt
    "gire", "vire", "girar", "virar", "rodar",
    # ja
    "回れ", "回って", "まわれ", "まわって",
    # zh
    "转", "旋转", "转动",
    # ko
    "돌아", "회전",
    # ru
    "повернись", "поверни", "крутись", "вращайся",
    # uk
    "повернись", "поверни", "крутись",
    # nl
    "draai", "draaien",
    # sv
    "sväng", "vrid", "svang",
    # cs + no-diacritics
    "otoč se", "toč", "otoc se", "toc",
    # tr
    "dön", "don", "döndür", "dondur",
}

# Time unit words (used in duration extraction)
_TIME_WORDS: set[str] = {
    # en
    "seconds", "second", "secs", "sec",
    # pl
    "sekund", "sekundy", "sekundę", "sekunde",
    # de
    "sekunden", "sekunde",
    # es/pt
    "segundos", "segundo",
    # fr
    "secondes", "seconde",
    # it
    "secondi", "secondo",
    # ja/zh
    "秒",
    # ko
    "초",
    # ru
    "секунд", "секунды", "секунду",
    # uk
    "секунд", "секунди", "секунду",
    # nl
    "seconden", "seconde",
    # sv
    "sekunder", "sekund",
    # cs + no-diacritics
    "vteřin", "vteřiny", "vterin", "vteriny",
    # tr
    "saniye",
}

MAX_DURATION = 10.0
DEFAULT_DURATION = 1.0

# Pre-compile a pattern to find a number (integer or decimal) in text
_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

# ---------------------------------------------------------------------------
# Whisper transcription normalization
# ---------------------------------------------------------------------------
# Whisper often romanizes non-Latin characters or drops diacritics in
# unpredictable ways. This table maps common phonetic outputs back to
# canonical forms so that keyword matching works even with bad transcriptions.

# Polish phonetic substitutions that Whisper commonly produces
_POLISH_PHONETIC_MAP = [
    # Whisper output -> canonical Polish (applied to keywords for matching)
    ("sz", "sh"), ("cz", "ch"), ("rz", "zh"), ("ść", "shch"),
    ("ś", "sh"), ("ć", "ch"), ("ź", "zh"), ("ż", "zh"),
    ("ą", "on"), ("ę", "en"), ("ł", "w"), ("ń", "n"),
    ("ó", "u"),
]


def _normalize_for_fuzzy(text: str) -> str:
    """Normalize text by converting Polish diacritics to their common
    Whisper romanization, so we can match against both forms."""
    result = text
    for polish, phonetic in _POLISH_PHONETIC_MAP:
        result = result.replace(polish, phonetic)
    return result


# Build a fuzzy-match version of action keywords: for each phrase,
# store both original and phonetically normalized form.
def _build_fuzzy_action_index():
    """Pre-compute normalized forms of all action keywords for fuzzy matching."""
    index = []  # list of (normalized_phrase, action)
    for phrases, action in _ACTION_KEYWORDS:
        for phrase in phrases:
            norm = _normalize_for_fuzzy(phrase)
            if norm != phrase:
                index.append((norm, action))
    return index


_FUZZY_ACTION_INDEX = _build_fuzzy_action_index()

# Similarly for stop words
_FUZZY_STOP_WORDS: set[str] = {_normalize_for_fuzzy(w) for w in _STOP_WORDS} - _STOP_WORDS


def _find_direction(text: str):
    """Return (x, y, z) unit vector and matched keyword, or None."""
    # Check longest phrases first to avoid partial matches
    for word in sorted(_DIRECTION_FORWARD, key=len, reverse=True):
        if word in text:
            return (1.0, 0.0, 0.0), word
    for word in sorted(_DIRECTION_BACKWARD, key=len, reverse=True):
        if word in text:
            return (-1.0, 0.0, 0.0), word
    for word in sorted(_DIRECTION_LEFT, key=len, reverse=True):
        if word in text:
            return (0.0, 1.0, 0.0), word
    for word in sorted(_DIRECTION_RIGHT, key=len, reverse=True):
        if word in text:
            return (0.0, -1.0, 0.0), word
    return None


def _find_verb(text: str):
    """Return verb type: 'run', 'move', 'turn', or None."""
    for word in sorted(_RUN_VERBS, key=len, reverse=True):
        if word in text:
            return "run"
    for word in sorted(_TURN_VERBS, key=len, reverse=True):
        if word in text:
            return "turn"
    for word in sorted(_MOVE_VERBS, key=len, reverse=True):
        if word in text:
            return "move"
    return None


def _find_duration(text: str) -> Optional[float]:
    """Extract duration in seconds from text, or None."""
    m = _NUMBER_RE.search(text)
    if m:
        try:
            val = float(m.group(1).replace(",", "."))
            if 0 < val <= MAX_DURATION:
                return val
        except ValueError:
            pass
    return None


def parse_command(text: str) -> ParsedCommand:
    """Parse transcribed voice text into a robot command."""
    if not text:
        return ParsedCommand(raw_text="")

    normalized = text.lower().strip()
    # Strip common punctuation
    normalized = re.sub(r"[.,!?;:。、！？]", "", normalized).strip()

    result = ParsedCommand(raw_text=text)

    # Check for stop command first (exact + fuzzy)
    if normalized in _STOP_WORDS or normalized in _FUZZY_STOP_WORDS:
        result.is_stop = True
        return result

    # Check for movement / rotation
    verb = _find_verb(normalized)
    direction_result = _find_direction(normalized)

    if verb == "turn" and direction_result:
        # Rotation: only care about left/right
        (_, dy, _), _ = direction_result
        if dy != 0.0:
            z = 1.0 if dy > 0 else -1.0  # left = positive z
        else:
            z = 0.0
        # Also support "turn left/right" without explicit direction from _find_direction
        # by checking left/right sets directly
        if z == 0.0:
            for w in _DIRECTION_LEFT:
                if w in normalized:
                    z = 1.0
                    break
            if z == 0.0:
                for w in _DIRECTION_RIGHT:
                    if w in normalized:
                        z = -1.0
                        break
        if z != 0.0:
            duration = _find_duration(normalized) or DEFAULT_DURATION
            result.timed_move = TimedMove(x=0.0, y=0.0, z=z, duration=duration)
            return result

    if direction_result and verb in ("move", "run", None):
        (dx, dy, dz), _ = direction_result
        speed = 1.0 if verb == "run" else 0.5
        duration = _find_duration(normalized) or DEFAULT_DURATION
        result.timed_move = TimedMove(
            x=dx * speed, y=dy * speed, z=dz * speed, duration=duration,
        )
        return result

    # Check one-shot action keywords (longer phrases first)
    for phrases, action in _ACTION_KEYWORDS:
        for phrase in phrases:
            if phrase in normalized:
                result.action = action
                return result

    # Fuzzy fallback: try phonetically normalized matching
    # This catches Whisper romanizations like "shad" for "siad", etc.
    fuzzy_normalized = _normalize_for_fuzzy(normalized)
    for norm_phrase, action in _FUZZY_ACTION_INDEX:
        if norm_phrase in fuzzy_normalized:
            result.action = action
            return result

    return result


# ---------------------------------------------------------------------------
# UI helpers: per-language command reference for the edit view
# ---------------------------------------------------------------------------

_COMMAND_REF: dict[str, list[tuple[str, str]]] = {
    "en": [
        ("sit, sit down", "Sit"),
        ("stand up, stand", "Stand up"),
        ("stand down, lie down", "Lie down"),
        ("stretch", "Stretch"),
        ("hello, wave, hi", "Wave hello"),
        ("jump", "Jump forward"),
        ("dance", "Dance"),
        ("finger heart, heart", "Finger heart"),
        ("flashlight, flash, light", "Toggle flashlight"),
        ("led, color", "Toggle LED color"),
        ("lidar", "Toggle lidar"),
        ("stop, halt, freeze", "Stop all movement"),
    ],
    "pl": [
        ("siad, siądź", "Siad"),
        ("wstań, wstawaj", "Wstań"),
        ("połóż się, leżeć", "Połóż się"),
        ("przeciągnij się", "Przeciągnij się"),
        ("cześć, hej, pomachaj", "Pomachaj"),
        ("skacz, skok", "Skok"),
        ("tańcz, taniec", "Taniec"),
        ("serce, serduszko", "Serduszko"),
        ("latarka, światło", "Latarka"),
        ("kolor, dioda", "Zmień kolor LED"),
        ("lidar", "Lidar"),
        ("stój, stop", "Stop"),
    ],
    "de": [
        ("sitz, setz dich", "Sitz"),
        ("steh auf, aufstehen", "Aufstehen"),
        ("leg dich hin, hinlegen", "Hinlegen"),
        ("strecken, streck dich", "Strecken"),
        ("hallo, winken", "Winken"),
        ("spring, sprung", "Springen"),
        ("tanz, tanzen", "Tanzen"),
        ("herz, finger herz", "Finger-Herz"),
        ("taschenlampe, licht", "Taschenlampe"),
        ("farbe, led", "LED-Farbe"),
        ("lidar", "Lidar"),
        ("stopp, halt, anhalten", "Stopp"),
    ],
    "es": [
        ("siéntate, sentarse", "Sentarse"),
        ("levántate, párate", "Levantarse"),
        ("acuéstate, échate", "Acostarse"),
        ("estírate, estirar", "Estirarse"),
        ("hola, saluda", "Saludar"),
        ("salta, saltar", "Saltar"),
        ("baila, bailar", "Bailar"),
        ("corazón", "Corazón"),
        ("linterna, luz", "Linterna"),
        ("color, led", "Color LED"),
        ("lidar", "Lidar"),
        ("para, alto, detente", "Detener"),
    ],
    "fr": [
        ("assis, assieds-toi", "S'asseoir"),
        ("lève-toi, debout", "Se lever"),
        ("couche-toi, allonge-toi", "Se coucher"),
        ("étire-toi, étirement", "S'étirer"),
        ("bonjour, salut, coucou", "Saluer"),
        ("saute, sauter", "Sauter"),
        ("danse, danser", "Danser"),
        ("coeur, cœur", "Coeur"),
        ("lampe, lumière", "Lampe"),
        ("couleur, led", "Couleur LED"),
        ("lidar", "Lidar"),
        ("arrête, stop", "Arrêter"),
    ],
    "it": [
        ("siediti, seduto", "Sedersi"),
        ("alzati, in piedi", "Alzarsi"),
        ("sdraiati, coricati", "Sdraiarsi"),
        ("stiracchiati, allungati", "Stiracchiarsi"),
        ("ciao, saluta", "Salutare"),
        ("salta, saltare", "Saltare"),
        ("balla, ballare", "Ballare"),
        ("cuore", "Cuore"),
        ("torcia, luce", "Torcia"),
        ("colore, led", "Colore LED"),
        ("lidar", "Lidar"),
        ("ferma, fermati", "Fermare"),
    ],
    "pt": [
        ("senta, sente", "Sentar"),
        ("levanta, levante", "Levantar"),
        ("deita, deite", "Deitar"),
        ("alongar, esticar", "Alongar"),
        ("olá, oi, acena", "Acenar"),
        ("pula, pular", "Pular"),
        ("dança, dançar", "Dançar"),
        ("coração", "Coração"),
        ("lanterna, luz", "Lanterna"),
        ("cor, led", "Cor LED"),
        ("lidar", "Lidar"),
        ("pare, parar", "Parar"),
    ],
    "ja": [
        ("座って, おすわり", "座る"),
        ("立って, 起きて", "立つ"),
        ("伏せて, 伏せ", "伏せる"),
        ("ストレッチ, 伸び", "ストレッチ"),
        ("こんにちは, ハロー", "挨拶"),
        ("ジャンプ, 跳べ", "ジャンプ"),
        ("ダンス, 踊って", "ダンス"),
        ("ハート, 指ハート", "ハート"),
        ("ライト, フラッシュ", "ライト"),
        ("カラー, 色", "LED色"),
        ("lidar", "Lidar"),
        ("ストップ, 止まれ", "停止"),
    ],
    "zh": [
        ("坐, 坐下", "坐下"),
        ("站起来, 起立", "站起来"),
        ("趴下, 躺下", "趴下"),
        ("伸展, 拉伸", "伸展"),
        ("你好, 挥手", "打招呼"),
        ("跳, 跳跃", "跳"),
        ("跳舞, 舞蹈", "跳舞"),
        ("比心, 爱心", "比心"),
        ("手电, 闪光灯", "手电筒"),
        ("颜色", "LED颜色"),
        ("lidar", "Lidar"),
        ("停, 停止", "停止"),
    ],
    "ko": [
        ("앉아, 앉아라", "앉기"),
        ("일어나, 일어서", "일어서기"),
        ("엎드려, 누워", "눕기"),
        ("스트레칭, 기지개", "스트레칭"),
        ("안녕, 인사", "인사"),
        ("점프, 뛰어", "점프"),
        ("춤, 댄스", "춤"),
        ("하트, 손가락 하트", "하트"),
        ("플래시, 손전등", "손전등"),
        ("색상, 컬러", "LED 색상"),
        ("라이다, lidar", "라이다"),
        ("멈춰, 정지", "정지"),
    ],
    "ru": [
        ("сядь, сесть", "Сесть"),
        ("встань, встать", "Встать"),
        ("ляг, ложись", "Лечь"),
        ("потянись, растяжка", "Растяжка"),
        ("привет, помаши", "Помахать"),
        ("прыгай, прыжок", "Прыжок"),
        ("танцуй, танец", "Танец"),
        ("сердце, сердечко", "Сердечко"),
        ("фонарик, свет", "Фонарик"),
        ("цвет, светодиод", "Цвет LED"),
        ("лидар, lidar", "Лидар"),
        ("стоп, стой", "Стоп"),
    ],
    "uk": [
        ("сідай, сядь", "Сісти"),
        ("встань, вставай", "Встати"),
        ("лягай, ляж", "Лягти"),
        ("потягнись, розтяжка", "Розтяжка"),
        ("привіт, помахай", "Помахати"),
        ("стрибай, стрибок", "Стрибок"),
        ("танцюй, танець", "Танець"),
        ("серце, серденько", "Серденько"),
        ("ліхтарик, світло", "Ліхтарик"),
        ("колір, світлодіод", "Колір LED"),
        ("лідар, lidar", "Лідар"),
        ("стоп, стій", "Стоп"),
    ],
    "nl": [
        ("zit, ga zitten", "Zitten"),
        ("sta op, opstaan", "Opstaan"),
        ("ga liggen, lig", "Liggen"),
        ("rek uit, stretch", "Strekken"),
        ("hallo, hoi, zwaai", "Zwaaien"),
        ("spring, sprong", "Springen"),
        ("dans, dansen", "Dansen"),
        ("hart", "Hart"),
        ("zaklamp, licht", "Zaklamp"),
        ("kleur, led", "LED kleur"),
        ("lidar", "Lidar"),
        ("stop, halt, sta stil", "Stop"),
    ],
    "sv": [
        ("sitt, sätt dig", "Sitta"),
        ("res dig, ställ dig upp", "Ställ dig upp"),
        ("lägg dig, ligg ner", "Ligga ner"),
        ("sträck, stretcha", "Sträcka"),
        ("hej, hejsan, vinka", "Vinka"),
        ("hoppa, hopp", "Hoppa"),
        ("dansa, dans", "Dansa"),
        ("hjärta", "Hjärta"),
        ("ficklampa, ljus", "Ficklampa"),
        ("färg, led", "LED-färg"),
        ("lidar", "Lidar"),
        ("stopp, stanna", "Stopp"),
    ],
    "cs": [
        ("sedni, sedni si", "Sednout"),
        ("vstaň, vstát", "Vstát"),
        ("lehni, lehni si", "Lehnout"),
        ("protáhni se", "Protažení"),
        ("ahoj, čau, zamávej", "Zamávat"),
        ("skoč, skákej", "Skočit"),
        ("tancuj, tanec", "Tancovat"),
        ("srdce, srdíčko", "Srdíčko"),
        ("svítilna, baterka", "Svítilna"),
        ("barva, led", "Barva LED"),
        ("lidar", "Lidar"),
        ("stůj, stop", "Stop"),
    ],
    "tr": [
        ("otur", "Otur"),
        ("kalk, ayağa kalk", "Kalk"),
        ("yat, uzan", "Yat"),
        ("gerin, esne", "Gerin"),
        ("merhaba, selam", "Selam"),
        ("zıpla, atla", "Zıpla"),
        ("dans et, oyna", "Dans"),
        ("kalp", "Kalp"),
        ("el feneri, fener", "El feneri"),
        ("renk, led", "LED renk"),
        ("lidar", "Lidar"),
        ("dur, stop", "Dur"),
    ],
}

_MOVEMENT_EXAMPLES: dict[str, list[str]] = {
    "en": [
        '"move forward 3 seconds"  /  "go left"',
        '"run backward 2 seconds"  (faster)',
        '"turn left 1 second"  /  "rotate right"',
    ],
    "pl": [
        '"idź do przodu 3 sekundy"  /  "idź w lewo"',
        '"biegnij do tyłu 2 sekundy"  (szybciej)',
        '"skręć w lewo 1 sekundę"  /  "obróć się w prawo"',
    ],
    "de": [
        '"geh vorwärts 3 Sekunden"  /  "geh links"',
        '"renn rückwärts 2 Sekunden"  (schneller)',
        '"dreh dich links 1 Sekunde"  /  "drehen rechts"',
    ],
    "es": [
        '"ve adelante 3 segundos"  /  "camina izquierda"',
        '"corre atrás 2 segundos"  (más rápido)',
        '"gira izquierda 1 segundo"  /  "gira derecha"',
    ],
    "fr": [
        '"va en avant 3 secondes"  /  "marche gauche"',
        '"cours en arrière 2 secondes"  (plus vite)',
        '"tourne gauche 1 seconde"  /  "tourne droite"',
    ],
    "it": [
        '"vai avanti 3 secondi"  /  "cammina sinistra"',
        '"corri indietro 2 secondi"  (più veloce)',
        '"gira sinistra 1 secondo"  /  "ruota destra"',
    ],
    "pt": [
        '"vá frente 3 segundos"  /  "ande esquerda"',
        '"corra trás 2 segundos"  (mais rápido)',
        '"gire esquerda 1 segundo"  /  "vire direita"',
    ],
    "ja": [
        '"進め 前 3秒"  /  "歩け 左"',
        '"走れ 後ろ 2秒"  (速い)',
        '"回れ 左 1秒"  /  "回って 右"',
    ],
    "zh": [
        '"走 前 3秒"  /  "移动 左"',
        '"跑 后 2秒"  (更快)',
        '"转 左 1秒"  /  "旋转 右"',
    ],
    "ko": [
        '"가 앞으로 3초"  /  "걸어 왼쪽"',
        '"달려 뒤로 2초"  (빠르게)',
        '"돌아 왼쪽 1초"  /  "회전 오른쪽"',
    ],
    "ru": [
        '"иди вперёд 3 секунды"  /  "шагай влево"',
        '"беги назад 2 секунды"  (быстрее)',
        '"повернись налево 1 секунду"  /  "поверни направо"',
    ],
    "uk": [
        '"іди вперед 3 секунди"  /  "рухайся вліво"',
        '"біжи назад 2 секунди"  (швидше)',
        '"повернись наліво 1 секунду"  /  "поверни направо"',
    ],
    "nl": [
        '"ga vooruit 3 seconden"  /  "loop links"',
        '"ren achteruit 2 seconden"  (sneller)',
        '"draai links 1 seconde"  /  "draai rechts"',
    ],
    "sv": [
        '"gå framåt 3 sekunder"  /  "gå vänster"',
        '"spring bakåt 2 sekunder"  (snabbare)',
        '"sväng vänster 1 sekund"  /  "vrid höger"',
    ],
    "cs": [
        '"jdi vpřed 3 vteřiny"  /  "jdi vlevo"',
        '"běž dozadu 2 vteřiny"  (rychleji)',
        '"otoč se doleva 1 vteřinu"  /  "toč doprava"',
    ],
    "tr": [
        '"git ileri 3 saniye"  /  "yürü sol"',
        '"koş geri 2 saniye"  (daha hızlı)',
        '"dön sol 1 saniye"  /  "dön sağ"',
    ],
}


def get_command_reference(lang: str = "en") -> list[tuple[str, str]]:
    """Return list of (phrases, action_description) for the given language."""
    return _COMMAND_REF.get(lang, _COMMAND_REF["en"])


def get_movement_examples(lang: str = "en") -> list[str]:
    """Return movement example strings for the given language."""
    examples = _MOVEMENT_EXAMPLES.get(lang, _MOVEMENT_EXAMPLES["en"])
    return examples + [f"Default duration: 1s, max: {MAX_DURATION:.0f}s"]
