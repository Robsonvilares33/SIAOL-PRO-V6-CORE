"""Auditoria de conferência e probabilidades com concursos oficiais fixados da CAIXA.

As amostras vêm dos endpoints públicos por concurso (links no README do teste).
Os cálculos de referência abaixo usam fórmulas combinatórias e enumeração de
subapostas, sem chamar rotinas internas de probabilidade do motor.
"""
from collections import Counter
from itertools import combinations
from math import comb
import unittest

from lotomaster.caixa import normalize_draw
from lotomaster.catalog import LOTTERIES
from lotomaster.engine import simulate_tickets, ticket_probability


# Payloads mínimos copiados dos resultados públicos oficiais por concurso.
# Mega-Sena: https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3088
# Lotofácil: https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil/3827
# Lotomania: https://servicebus2.caixa.gov.br/portaldeloterias/api/lotomania/3000
# Quina: https://servicebus2.caixa.gov.br/portaldeloterias/api/quina/7161
# Dia de Sorte: https://servicebus2.caixa.gov.br/portaldeloterias/api/diadesorte/1334
# Dupla Sena: https://servicebus2.caixa.gov.br/portaldeloterias/api/duplasena/3034
# Timemania: https://servicebus2.caixa.gov.br/portaldeloterias/api/timemania/2455
# Super Sete: https://servicebus2.caixa.gov.br/portaldeloterias/api/supersete/909
# +Milionária: https://servicebus2.caixa.gov.br/portaldeloterias/api/maismilionaria/405
OFFICIAL_PAYLOADS = {
    "megasena": {
        "numero": 3088, "dataApuracao": "19/11/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "MEGA_SENA", "listaDezenas": ["10", "21", "24", "28", "34", "44"],
        "dezenasSorteadasOrdemSorteio": ["34", "44", "21", "10", "28", "24"],
    },
    "lotofacil": {
        "numero": 3827, "dataApuracao": "11/11/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "LOTOFACIL",
        "listaDezenas": ["01", "02", "04", "05", "06", "10", "11", "13", "15", "16", "18", "20", "21", "22", "23"],
        "dezenasSorteadasOrdemSorteio": ["10", "11", "23", "06", "02", "20", "13", "21", "16", "18", "05", "01", "04", "15", "22"],
    },
    "lotomania": {
        "numero": 3000, "dataApuracao": "16/11/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "LOTOMANIA",
        "listaDezenas": ["00", "05", "07", "11", "19", "21", "24", "36", "37", "38", "46", "48", "59", "69", "74", "75", "81", "92", "95", "99"],
        "dezenasSorteadasOrdemSorteio": ["74", "46", "05", "92", "11", "36", "69", "37", "81", "48", "75", "21", "38", "99", "95", "24", "07", "19", "00", "59"],
    },
    "quina": {
        "numero": 7161, "dataApuracao": "06/11/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "QUINA", "listaDezenas": ["48", "53", "68", "71", "79"],
        "dezenasSorteadasOrdemSorteio": ["79", "71", "53", "48", "68"],
    },
    "diadesorte": {
        "numero": 1334, "dataApuracao": "28/10/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "DIA_DE_SORTE", "listaDezenas": ["02", "04", "06", "08", "09", "22", "25"],
        "dezenasSorteadasOrdemSorteio": ["04", "25", "02", "09", "08", "06", "22"],
        "nomeTimeCoracaoMesSorte": "Outubro",
    },
    "duplasena": {
        "numero": 3034, "dataApuracao": "18/11/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "DUPLA_SENA", "listaDezenas": ["08", "11", "15", "22", "28", "37"],
        "dezenasSorteadasOrdemSorteio": ["08", "22", "15", "11", "28", "37", "23", "19", "30", "22", "28", "48"],
        "listaDezenasSegundoSorteio": ["19", "22", "23", "28", "30", "48"],
    },
    "timemania": {
        "numero": 2455, "dataApuracao": "15/10/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "TIMEMANIA", "listaDezenas": ["07", "28", "31", "32", "60", "61", "76"],
        "dezenasSorteadasOrdemSorteio": ["31", "60", "28", "32", "07", "61", "76"],
        "nomeTimeCoracaoMesSorte": "LONDRINA /PR",
    },
    "supersete": {
        "numero": 909, "dataApuracao": "09/10/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "SUPER_SETE", "listaDezenas": ["8", "7", "6", "6", "0", "5", "4"],
        "dezenasSorteadasOrdemSorteio": ["8", "7", "6", "6", "0", "5", "4"],
    },
    "maismilionaria": {
        "numero": 405, "dataApuracao": "06/11/2026", "indicadorConcursoEspecial": 1,
        "tipoJogo": "MAIS_MILIONARIA", "listaDezenas": ["01", "15", "21", "32", "34", "41"],
        "dezenasSorteadasOrdemSorteio": ["32", "15", "41", "01", "21", "34", "03", "04"],
        "trevosSorteados": ["3", "4"],
    },
}


def _hypergeometric(population, picks, draw_size):
    minimum = max(0, draw_size - (population - picks))
    maximum = min(picks, draw_size)
    return {
        hits: comb(picks, hits) * comb(population - picks, draw_size - hits)
        for hits in range(minimum, maximum + 1)
    }, comb(population, draw_size)


def _check_hit_distribution(result, expected, denominator):
    actual = {row["hits"]: row for row in result["hit_distribution"]}
    assert set(actual) == set(expected)
    for hits, favorable in expected.items():
        assert actual[hits]["favorable_outcomes"] == str(favorable)
        assert actual[hits]["total_outcomes"] == str(denominator)


def _super_seven_reference(column_picks):
    counts = [1]
    for picks in column_picks:
        updated = [0] * (len(counts) + 1)
        for hits in range(len(counts)):
            updated[hits] += counts[hits] * (10 - picks)
            updated[hits + 1] += counts[hits] * picks
        counts = updated
    return counts, 10 ** len(column_picks)


def _official_million_tier(main_hits, trevo_hits):
    if main_hits == 6:
        return 1 if trevo_hits == 2 else 2
    if main_hits == 5:
        return 3 if trevo_hits == 2 else 4
    if main_hits == 4:
        return 5 if trevo_hits == 2 else 6
    if main_hits == 3:
        return 7 if trevo_hits == 2 else (8 if trevo_hits == 1 else None)
    if main_hits == 2:
        return 9 if trevo_hits == 2 else (10 if trevo_hits == 1 else None)
    return None


def _million_probability_by_subbet_enumeration(picks, trevo_count):
    """Enumerate every elementary ticket line for each sufficient intersection state."""
    total_main = comb(50, 6)
    total_trevos = comb(6, 2)
    tier_presence = Counter()
    any_prize = 0
    picked_numbers = tuple(range(picks))
    outside_numbers = tuple(range(picks, 50))
    picked_trevos = tuple(range(trevo_count))
    outside_trevos = tuple(range(trevo_count, 6))
    main_lines = tuple(combinations(picked_numbers, 6))
    trevo_lines = tuple(combinations(picked_trevos, 2))

    for main_hits in range(7):
        main_state_count = comb(picks, main_hits) * comb(50 - picks, 6 - main_hits)
        if not main_state_count:
            continue
        drawn_numbers = set(range(main_hits)) | set(outside_numbers[:6 - main_hits])
        for trevo_hits in range(3):
            trevo_state_count = comb(trevo_count, trevo_hits) * comb(6 - trevo_count, 2 - trevo_hits)
            if not trevo_state_count:
                continue
            drawn_trevos = set(range(trevo_hits)) | set(outside_trevos[:2 - trevo_hits])
            seen_tiers = set()
            for line_numbers in main_lines:
                number_hits = len(set(line_numbers) & drawn_numbers)
                for line_trevos in trevo_lines:
                    bonus_hits = len(set(line_trevos) & drawn_trevos)
                    tier = _official_million_tier(number_hits, bonus_hits)
                    if tier is not None:
                        seen_tiers.add(tier)
            state_count = main_state_count * trevo_state_count
            if seen_tiers:
                any_prize += state_count
                for tier in seen_tiers:
                    tier_presence[tier] += state_count

    return tier_presence, any_prize, total_main * total_trevos


class OfficialDrawProbabilityAuditTests(unittest.TestCase):
    def test_all_nine_official_records_normalize_with_bonus_and_column_fields(self):
        self.assertEqual(set(OFFICIAL_PAYLOADS), set(LOTTERIES))
        normalized = {game: normalize_draw(game, payload) for game, payload in OFFICIAL_PAYLOADS.items()}
        self.assertEqual({game: row["contest"] for game, row in normalized.items()}, {
            "megasena": 3088, "lotofacil": 3827, "lotomania": 3000, "quina": 7161,
            "diadesorte": 1334, "duplasena": 3034, "timemania": 2455,
            "supersete": 909, "maismilionaria": 405,
        })
        self.assertEqual(normalized["diadesorte"]["month"], {"name": "Outubro", "number": 10})
        self.assertEqual(normalized["timemania"]["team"], "LONDRINA /PR")
        self.assertEqual(normalized["duplasena"]["second_numbers"], [19, 22, 23, 28, 30, 48])
        self.assertEqual(normalized["maismilionaria"]["trevos"], [3, 4])
        self.assertEqual(normalized["supersete"]["numbers"], [8, 7, 6, 6, 0, 5, 4])
        self.assertTrue(all(not row["special_draw"] for row in normalized.values()))

    def test_official_regular_and_mega_da_virada_indicators_are_distinct(self):
        # Official records: /megasena/2810 is Mega da Virada (31/12/2024),
        # while /megasena/2811 is a regular draw (04/01/2025).
        regular = normalize_draw("megasena", {
            "numero": 2811, "dataApuracao": "04/01/2025", "indicadorConcursoEspecial": 1,
            "listaDezenas": ["08", "27", "36", "37", "39", "45"],
        })
        special = normalize_draw("megasena", {
            "numero": 2810, "dataApuracao": "31/12/2024", "indicadorConcursoEspecial": 2,
            "listaDezenas": ["01", "17", "19", "29", "50", "57"],
        })
        self.assertFalse(regular["special_draw"])
        self.assertTrue(special["special_draw"])

    def test_official_draw_ticket_checking_matches_components_and_independent_million_subbet_enumeration(self):
        draws = {game: normalize_draw(game, payload) for game, payload in OFFICIAL_PAYLOADS.items()}
        checks = {
            "megasena": ([{"numbers": draws["megasena"]["numbers"]}], 6, "6 acertos"),
            "lotofacil": ([{"numbers": draws["lotofacil"]["numbers"]}], 15, "15 acertos"),
            "quina": ([{"numbers": draws["quina"]["numbers"]}], 5, "5 acertos"),
        }
        for game, (tickets, hits, award) in checks.items():
            with self.subTest(game=game):
                row = simulate_tickets(game, tickets, draws[game])[0]
                self.assertEqual(row["main_hits"], hits)
                self.assertEqual(row["award"], award)

        lm_winning = set(draws["lotomania"]["numbers"])
        lm_outside = [number for number in range(100) if number not in lm_winning]
        lm_ticket = {"numbers": sorted(lm_winning | set(lm_outside[:30]))}
        lm_result = simulate_tickets("lotomania", [lm_ticket], draws["lotomania"])[0]
        self.assertEqual(lm_result["main_hits"], 20)
        self.assertEqual(lm_result["award"], "20 acertos")

        day_ticket = {"numbers": draws["diadesorte"]["numbers"], "bonus": {"month": 10}}
        day_result = simulate_tickets("diadesorte", [day_ticket], draws["diadesorte"])[0]
        self.assertEqual(day_result["main_hits"], 7)
        self.assertTrue(day_result["month_hit"])

        double_ticket = {"numbers": [8, 11, 15, 22, 23, 30]}
        double_result = simulate_tickets("duplasena", [double_ticket], draws["duplasena"])[0]
        self.assertEqual((double_result["main_hits"], double_result["second_hits"]), (4, 3))
        self.assertEqual(double_result["award"], {"first": "4 acertos", "second": "3 acertos"})

        team_ticket = {"numbers": [7, 28, 31, 32, 60, 61, 76, 1, 2, 3], "bonus": {"team": "londrina /pr"}}
        team_result = simulate_tickets("timemania", [team_ticket], draws["timemania"])[0]
        self.assertEqual(team_result["main_hits"], 7)
        self.assertTrue(team_result["team_hit"])

        super_ticket = {"columns": [[digit] for digit in draws["supersete"]["numbers"]]}
        super_result = simulate_tickets("supersete", [super_ticket], draws["supersete"])[0]
        self.assertEqual(super_result["hits"], 7)
        self.assertEqual(super_result["award"], "7 acertos")

        million_draw = draws["maismilionaria"]
        million_numbers = million_draw["numbers"] + [n for n in range(1, 51) if n not in million_draw["numbers"]][:6]
        million_trevos = [1, 2, 3, 4, 5, 6]
        million_ticket = {"numbers": million_numbers, "bonus": {"trevos": million_trevos}}
        million_result = simulate_tickets("maismilionaria", [million_ticket], million_draw)[0]
        expected = Counter()
        for line_numbers in combinations(million_numbers, 6):
            number_hits = len(set(line_numbers) & set(million_draw["numbers"]))
            for line_trevos in combinations(million_trevos, 2):
                bonus_hits = len(set(line_trevos) & set(million_draw["trevos"]))
                tier = _official_million_tier(number_hits, bonus_hits)
                if tier is not None:
                    labels = {
                        1: "Faixa 1 · 6 acertos + 2 trevos",
                        2: "Faixa 2 · 6 acertos + 1 ou nenhum trevo",
                        3: "Faixa 3 · 5 acertos + 2 trevos",
                        4: "Faixa 4 · 5 acertos + 1 ou nenhum trevo",
                        5: "Faixa 5 · 4 acertos + 2 trevos",
                        6: "Faixa 6 · 4 acertos + 1 ou nenhum trevo",
                        7: "Faixa 7 · 3 acertos + 2 trevos",
                        8: "Faixa 8 · 3 acertos + 1 trevo",
                        9: "Faixa 9 · 2 acertos + 2 trevos",
                        10: "Faixa 10 · 2 acertos + 1 trevo",
                    }
                    expected[labels[tier]] += 1
        self.assertEqual(million_result["main_hits"], 6)
        self.assertEqual(million_result["trevo_hits"], 2)
        self.assertEqual(million_result["subbets_total"], comb(12, 6) * comb(6, 2))
        self.assertEqual(million_result["award_counts"], dict(expected))
        self.assertEqual(million_result["winning_subbets"], sum(expected.values()))

    def test_theoretical_probability_distributions_match_independent_exact_counts(self):
        picks_by_game = {
            "megasena": 7, "lotofacil": 17, "lotomania": 50, "quina": 7,
            "diadesorte": 9, "duplasena": 6, "timemania": 10,
            "maismilionaria": 7,
        }
        rules = {
            "megasena": (60, 6, {4, 5, 6}),
            "lotofacil": (25, 15, {11, 12, 13, 14, 15}),
            "lotomania": (100, 20, {0, 15, 16, 17, 18, 19, 20}),
            "quina": (80, 5, {2, 3, 4, 5}),
            "diadesorte": (31, 7, {4, 5, 6, 7}),
            "duplasena": (50, 6, {3, 4, 5, 6}),
            "timemania": (80, 7, {3, 4, 5, 6, 7}),
            "maismilionaria": (50, 6, {2, 3, 4, 5, 6}),
        }
        for game, (population, draw_size, prize_hits) in rules.items():
            with self.subTest(game=game):
                picks = picks_by_game[game]
                main_counts, denominator = _hypergeometric(population, picks, draw_size)
                kwargs = {"pick_count": picks}
                if game == "maismilionaria":
                    kwargs["trevo_count"] = 3
                result = ticket_probability(game, **kwargs)
                if game == "duplasena":
                    best_counts = {}
                    cumulative = 0
                    previous = 0
                    for hits, count in sorted(main_counts.items()):
                        cumulative += count
                        best_counts[hits] = cumulative ** 2 - previous
                        previous = cumulative ** 2
                    _check_hit_distribution(result, best_counts, denominator ** 2)
                else:
                    _check_hit_distribution(result, main_counts, denominator)

                main_wins = sum(main_counts.get(hits, 0) for hits in prize_hits)
                if game in {"megasena", "lotofacil", "lotomania", "quina"}:
                    any_favorable, any_total = main_wins, denominator
                elif game == "diadesorte":
                    any_favorable, any_total = main_wins * 12 + (denominator - main_wins), denominator * 12
                elif game == "timemania":
                    any_favorable, any_total = main_wins * 80 + (denominator - main_wins), denominator * 80
                elif game == "duplasena":
                    any_favorable, any_total = denominator ** 2 - (denominator - main_wins) ** 2, denominator ** 2
                else:
                    _, any_favorable, any_total = _million_probability_by_subbet_enumeration(picks, 3)
                self.assertEqual(result["any_prize"]["favorable_outcomes"], str(any_favorable))
                self.assertEqual(result["any_prize"]["total_outcomes"], str(any_total))

        column_picks = [1, 2, 3, 4, 5, 6, 7]
        expected_super, super_total = _super_seven_reference(column_picks)
        super_result = ticket_probability("supersete", column_pick_counts=column_picks)
        _check_hit_distribution(super_result, dict(enumerate(expected_super)), super_total)
        self.assertEqual(
            super_result["any_prize"]["favorable_outcomes"],
            str(sum(expected_super[3:])),
        )
        self.assertEqual(super_result["any_prize"]["total_outcomes"], str(super_total))

        million_result = ticket_probability("maismilionaria", pick_count=7, trevo_count=3)
        tier_presence, _, million_total = _million_probability_by_subbet_enumeration(7, 3)
        actual_tiers = {row["tier"]: row for row in million_result["prize_tiers"]}
        self.assertEqual(set(actual_tiers), set(range(1, 11)))
        for tier, favorable in tier_presence.items():
            self.assertEqual(actual_tiers[tier]["favorable_outcomes"], str(favorable))
            self.assertEqual(actual_tiers[tier]["total_outcomes"], str(million_total))


if __name__ == "__main__":
    unittest.main()
