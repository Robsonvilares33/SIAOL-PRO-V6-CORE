import unittest
from unittest.mock import Mock, patch

from lotomaster.caixa import fetch_draw, normalize_draw
from lotomaster.catalog import LOTTERIES
from lotomaster.engine import latest_result


def valid_payload(game):
    spec = LOTTERIES[game]
    numbers = list(range(spec["minimum"], spec["minimum"] + spec["draw_size"]))
    # A lottery's range always has enough distinct base values except Super Sete,
    # where repeated digits across its seven columns are explicitly legitimate.
    payload = {"numero": 123, "listaDezenas": [f"{n:02d}" for n in numbers]}
    if game == "supersete":
        payload["listaDezenas"] = ["0", "1", "0", "3", "4", "5", "6"]
    if game == "duplasena":
        payload["listaDezenasSegundoSorteio"] = ["08", "16", "31", "35", "44", "47"]
    if game == "diadesorte":
        payload["nomeTimeCoracaoMesSorte"] = "Janeiro"
    if game == "timemania":
        payload["nomeTimeCoracaoMesSorte"] = "TIME/UF"
    if game == "maismilionaria":
        payload["trevosSorteados"] = ["3", "6"]
    return payload


class CaixaValidationTests(unittest.TestCase):
    def test_valid_synthetic_payloads_cover_every_catalog_modality(self):
        for game in LOTTERIES:
            with self.subTest(game=game):
                draw = normalize_draw(game, valid_payload(game))
                self.assertEqual(draw["game"], game)
                self.assertEqual(draw["contest"], 123)
                self.assertEqual(len(draw["numbers"]), LOTTERIES[game]["draw_size"])
        self.assertEqual(normalize_draw("supersete", valid_payload("supersete"))["numbers"], [0, 1, 0, 3, 4, 5, 6])

    def test_valid_special_ordered_encodings_are_preserved(self):
        dupla = valid_payload("duplasena")
        dupla.pop("listaDezenasSegundoSorteio")
        dupla["listaDezenas"] = ["03", "11", "17", "22", "29", "39"]
        dupla["dezenasSorteadasOrdemSorteio"] = ["03", "11", "17", "22", "29", "39", "08", "16", "31", "35", "44", "47"]
        result = normalize_draw("duplasena", dupla)
        self.assertEqual(result["second_numbers"], [8, 16, 31, 35, 44, 47])

        milionaria = valid_payload("maismilionaria")
        milionaria.pop("trevosSorteados")
        milionaria.pop("listaDezenas")
        milionaria["dezenasSorteadasOrdemSorteio"] = ["06", "15", "28", "30", "42", "50", "03", "06"]
        result = normalize_draw("maismilionaria", milionaria)
        self.assertEqual(result["trevos"], [3, 6])
        self.assertEqual(result["numbers"], [6, 15, 28, 30, 42, 50])

    def test_maismilionaria_accepts_trevo_value_one(self):
        payload = valid_payload("maismilionaria")
        payload["trevosSorteados"] = ["1", "6"]
        result = normalize_draw("maismilionaria", payload)
        self.assertEqual(result["trevos"], [1, 6])

    def test_rejects_incomplete_out_of_range_duplicate_and_non_integer_numbers(self):
        cases = []
        for field, value in (
            ("listaDezenas", ["01", "02", "03"]),
            ("listaDezenas", ["00", "02", "03", "04", "05", "06"]),
            ("listaDezenas", ["01", "02", "03", "04", "05", "05"]),
            ("listaDezenas", ["01", "02", "03", "04", "05", 6.0]),
            ("listaDezenas", ["01", "02", "03", "04", "05", True]),
        ):
            payload = valid_payload("megasena")
            payload[field] = value
            cases.append(payload)
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                normalize_draw("megasena", payload)

    def test_rejects_invalid_special_draw_components(self):
        bad = valid_payload("duplasena")
        bad["listaDezenasSegundoSorteio"] = ["01", "02"]
        with self.assertRaisesRegex(ValueError, "listaDezenasSegundoSorteio"):
            normalize_draw("duplasena", bad)

        bad = valid_payload("maismilionaria")
        bad["trevosSorteados"] = ["3", "3"]
        with self.assertRaisesRegex(ValueError, "duplicadas"):
            normalize_draw("maismilionaria", bad)

        for game in ("diadesorte", "timemania"):
            bad = valid_payload(game)
            bad.pop("nomeTimeCoracaoMesSorte")
            with self.subTest(game=game), self.assertRaises(ValueError):
                normalize_draw(game, bad)

    def test_rejects_bad_contest_dates_awards_and_money(self):
        mutations = (
            ("numero", 0),
            ("numero", True),
            ("dataApuracao", "31/02/2026"),
            ("listaRateioPremio", {"bad": "shape"}),
            ("valorEstimadoProximoConcurso", float("nan")),
        )
        for field, value in mutations:
            payload = valid_payload("megasena")
            payload[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                normalize_draw("megasena", payload)

    def test_fetch_rejects_invalid_payload_and_contest_mismatch(self):
        response = Mock()
        response.json.return_value = valid_payload("megasena")
        with patch("lotomaster.caixa.requests.get", return_value=response):
            with self.assertRaisesRegex(ValueError, "em vez do concurso"):
                fetch_draw("megasena", 124)
            response.json.return_value["listaDezenas"] = ["01"]
            with self.assertRaises(ValueError):
                fetch_draw("megasena")

    def test_invalid_caixa_response_cannot_be_saved_as_official_result(self):
        with (
            patch("lotomaster.engine.storage.latest_draw", return_value=None),
            patch("lotomaster.engine.fetch_draw", side_effect=ValueError("resultado inválido")),
            patch("lotomaster.engine.storage.save_draw") as save,
        ):
            with self.assertRaisesRegex(RuntimeError, "Não foi possível consultar a CAIXA") as error:
                latest_result("megasena", refresh=True)
            self.assertNotIn("resultado inválido", str(error.exception))
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
