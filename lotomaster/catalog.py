"""Catálogo das modalidades Lotomaster, baseado em regras públicas da CAIXA e páginas públicas do MazuSoft."""
from copy import deepcopy

COMMON_STATS = [
    ("analysis", "Tabela de Análise dos Números"),
    ("behavior", "Comportamento das Dezenas"),
    ("cycles", "Ciclo das Dezenas"),
    ("frequency", "Frequência dos Números mais Sorteados"),
    ("delays", "Sequências e Atrasos"),
    ("parity", "Pares e Ímpares"),
    ("repeats", "Repetidas do Concurso Anterior"),
    ("primes", "Números Primos"),
    ("sums", "Somas dos Números"),
    ("fibonacci", "Números de Fibonacci"),
    ("multiples3", "Números Múltiplos de Três"),
    ("order", "Ordem de Sorteio e Posição Detalhada"),
    ("pareto", "Princípio de Pareto"),
    ("lines-columns", "Dezenas por Linhas e Colunas"),
    ("frame-center", "Dezenas na Moldura e Centro"),
    ("missing", "Tabela de Dezenas Ausentes"),
    ("duos", "Tabela dos Duques (Duplas de Números)"),
    ("trios", "Tabela das Trincas (Trios de Números)"),
    ("patterns", "Tabela de Padrões"),
    ("colors", "Cores das Bolas Sorteadas"),
    ("sequence-jumps", "Sequências e Saltos das Dezenas"),
    ("binary", "Tabela Binária"),
    ("filters", "Tabela dos Filtros"),
]

LOTTERIES = {
    "megasena": {
        "key": "megasena", "name": "Mega-Sena", "slug": "mega", "endpoint": "megasena",
        "minimum": 1, "maximum": 60, "draw_size": 6, "pick_size": 6,
        "min_pick": 6, "max_pick": 20, "digits": 2, "draws_per_contest": 1,
        "bonus": None, "prize_hits": [4, 5, 6],
        "extra_stats": [("quadrants", "Tabela dos Quadrantes"), ("special-draw", "Mega da Virada")],
    },
    "lotofacil": {
        "key": "lotofacil", "name": "Lotofácil", "slug": "lotofacil", "endpoint": "lotofacil",
        "minimum": 1, "maximum": 25, "draw_size": 15, "pick_size": 15,
        "min_pick": 15, "max_pick": 20, "digits": 2, "draws_per_contest": 1,
        "bonus": None, "prize_hits": [11, 12, 13, 14, 15],
        "extra_stats": [("independencia", "Lotofácil da Independência"), ("final-zero", "Concursos Final Zero"), ("suits", "Tabela de Naipes")],
    },
    "lotomania": {
        "key": "lotomania", "name": "Lotomania", "slug": "lotomania", "endpoint": "lotomania",
        "minimum": 0, "maximum": 99, "draw_size": 20, "pick_size": 50,
        "min_pick": 50, "max_pick": 50, "digits": 2, "draws_per_contest": 1,
        "bonus": None, "prize_hits": [0, 15, 16, 17, 18, 19, 20],
        "extra_stats": [("quadrants", "Dezenas por Quadrantes")],
    },
    "quina": {
        "key": "quina", "name": "Quina", "slug": "quina", "endpoint": "quina",
        "minimum": 1, "maximum": 80, "draw_size": 5, "pick_size": 5,
        "min_pick": 5, "max_pick": 15, "digits": 2, "draws_per_contest": 1,
        "bonus": None, "prize_hits": [2, 3, 4, 5],
        "extra_stats": [("final-five", "Concursos Final Cinco da Quina"), ("quina-sao-joao", "Quina de São João")],
    },
    "diadesorte": {
        "key": "diadesorte", "name": "Dia de Sorte", "slug": "dia-de-sorte", "endpoint": "diadesorte",
        "minimum": 1, "maximum": 31, "draw_size": 7, "pick_size": 7,
        "min_pick": 7, "max_pick": 15, "digits": 2, "draws_per_contest": 1,
        "bonus": {"type": "month", "label": "Mês da Sorte", "minimum": 1, "maximum": 12},
        "prize_hits": [4, 5, 6, 7],
        "extra_stats": [("months", "Frequência dos Meses mais Sorteados"), ("months-repeat", "Meses Repetidos e Atrasados")],
    },
    "duplasena": {
        "key": "duplasena", "name": "Dupla Sena", "slug": "dupla-sena", "endpoint": "duplasena",
        "minimum": 1, "maximum": 50, "draw_size": 6, "pick_size": 6,
        "min_pick": 6, "max_pick": 15, "digits": 2, "draws_per_contest": 2,
        "bonus": None, "prize_hits": [3, 4, 5, 6],
        "extra_stats": [("second-draw", "Análise dos Dois Sorteios"), ("easter", "Dupla Sena de Páscoa")],
    },
    "timemania": {
        "key": "timemania", "name": "Timemania", "slug": "timemania", "endpoint": "timemania",
        "minimum": 1, "maximum": 80, "draw_size": 7, "pick_size": 10,
        "min_pick": 10, "max_pick": 10, "digits": 2, "draws_per_contest": 1,
        "bonus": {"type": "team", "label": "Time do Coração"}, "prize_hits": [3, 4, 5, 6, 7],
        "extra_stats": [("teams", "Frequência dos Times mais Sorteados"), ("team-delays", "Sequências e Atrasos dos Times")],
    },
    "supersete": {
        "key": "supersete", "name": "Super Sete", "slug": "super-sete", "endpoint": "supersete",
        "minimum": 0, "maximum": 9, "draw_size": 7, "pick_size": 7,
        "min_pick": 7, "max_pick": 7, "digits": 1, "draws_per_contest": 1,
        "bonus": {"type": "columns", "label": "Colunas", "count": 7}, "prize_hits": [3, 4, 5, 6, 7],
        "extra_stats": [("column-frequency", "Frequência por Coluna"), ("column-cycles", "Ciclos dos Números por Coluna")],
    },
    "maismilionaria": {
        "key": "maismilionaria", "name": "+Milionária", "slug": "mais-milionaria", "endpoint": "maismilionaria",
        "minimum": 1, "maximum": 50, "draw_size": 6, "pick_size": 6,
        "min_pick": 6, "max_pick": 6, "digits": 2, "draws_per_contest": 1,
        "bonus": {"type": "trevos", "label": "Trevos da Sorte", "minimum": 2, "maximum": 6, "draw_size": 2},
        "prize_hits": [2, 3, 4, 5, 6],
        "extra_stats": [("trevos", "Frequência dos Trevos da Sorte"), ("trevo-pairs", "Combinações dos Trevos da Sorte"), ("trevo-order", "Ordem de Sorteio dos Trevos")],
    },
}


def get_spec(key: str) -> dict:
    normalized = (key or "").strip().lower().replace("+", "mais")
    for item in LOTTERIES.values():
        if normalized in {item["key"], item["slug"], item["endpoint"]}:
            return item
    aliases = {"mega-sena": "megasena", "dia-de-sorte": "diadesorte", "dupla-sena": "duplasena", "super-sete": "supersete", "mais-milionaria": "maismilionaria", "milionaria": "maismilionaria"}
    if normalized in aliases:
        return LOTTERIES[aliases[normalized]]
    raise KeyError(key)


def get_stats(spec: dict) -> list[dict]:
    items = list(COMMON_STATS) + list(spec.get("extra_stats", []))
    seen = set()
    result = []
    for key, label in items:
        if key not in seen:
            result.append({"id": key, "label": label})
            seen.add(key)
    return result


def public_spec(spec: dict) -> dict:
    result = deepcopy(spec)
    result["range"] = {"minimum": spec["minimum"], "maximum": spec["maximum"]}
    result["statistics"] = get_stats(spec)
    for internal in ("minimum", "maximum", "extra_stats"):
        result.pop(internal, None)
    return result


def public_catalog() -> list[dict]:
    return [public_spec(spec) for spec in LOTTERIES.values()]
