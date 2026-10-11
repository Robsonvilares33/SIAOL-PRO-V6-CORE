"""Estatísticas descritivas sobre concursos históricos; não são previsões de resultados."""
from collections import Counter
from itertools import combinations
import math

from .catalog import get_spec, get_stats


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    return all(n % d for d in range(2, int(math.sqrt(n)) + 1))


def _fibonacci(limit: int) -> set[int]:
    values = {0, 1}
    a, b = 0, 1
    while b <= limit:
        values.add(b)
        a, b = b, a + b
    return values


def _number_values(draw: dict, key: str) -> list[int]:
    if key == "duplasena":
        return list(draw.get("numbers", []))
    return list(draw.get("numbers", []))


def analyze_draws(game: str, draws: list[dict]) -> dict:
    spec = get_spec(game)
    key = spec["key"]
    ordered_draws = sorted(draws or [], key=lambda d: int(d.get("contest", 0)), reverse=True)
    n_draws = len(ordered_draws)
    low, high = spec["minimum"], spec["maximum"]
    pool = list(range(low, high + 1))
    all_numbers = [_number_values(d, key) for d in ordered_draws]
    counts = Counter(n for row in all_numbers for n in row)
    denominator = max(n_draws, 1)
    frequency = []
    gaps = []
    for number in pool:
        gap = next((i for i, row in enumerate(all_numbers) if number in row), n_draws)
        frequency.append({
            "number": number,
            "count": counts[number],
            "percent": round(counts[number] * 100 / denominator, 2),
            "gap": gap,
        })
        gaps.append({"number": number, "draws_since_hit": gap})
    frequency.sort(key=lambda row: (-row["count"], row["number"]))
    gaps.sort(key=lambda row: (-row["draws_since_hit"], row["number"]))

    sums = [sum(row) for row in all_numbers]
    even_odd = Counter((sum(n % 2 == 0 for n in row), sum(n % 2 != 0 for n in row)) for row in all_numbers)
    repeated = []
    for i in range(len(all_numbers) - 1):
        current = set(all_numbers[i])
        previous = set(all_numbers[i + 1])
        repeated.append(len(current & previous))
    pair_counts = Counter()
    triple_counts = Counter()
    for row in all_numbers:
        unique = sorted(set(row))
        pair_counts.update(combinations(unique, 2))
        if key != "supersete":
            triple_counts.update(combinations(unique, 3))
    pairs = [{"numbers": list(pair), "count": count} for pair, count in pair_counts.most_common(20)]
    triples = [{"numbers": list(triple), "count": count} for triple, count in triple_counts.most_common(15)]

    primes = [n for n in pool if _is_prime(n)]
    fibonacci = sorted(_fibonacci(high) & set(pool))
    prime_hits = sum(n in primes for row in all_numbers for n in row)
    fibonacci_hits = sum(n in fibonacci for row in all_numbers for n in row)
    multiple3_hits = sum(n % 3 == 0 for row in all_numbers for n in row)
    missing = [n for n in pool if counts[n] == 0]
    consecutive = Counter()
    for row in all_numbers:
        values = sorted(set(row))
        run = 1
        for index in range(1, len(values)):
            if values[index] == values[index - 1] + 1:
                run += 1
            else:
                if run >= 2:
                    consecutive[run] += 1
                run = 1
        if run >= 2:
            consecutive[run] += 1

    sum_summary = {
        "count": len(sums),
        "mean": round(sum(sums) / len(sums), 2) if sums else 0,
        "min": min(sums) if sums else 0,
        "max": max(sums) if sums else 0,
        "latest": sums[0] if sums else 0,
        "distribution": [{"sum": s, "count": c} for s, c in sorted(Counter(sums).items())],
    }
    parity_rows = [
        {"even": pair[0], "odd": pair[1], "count": count}
        for pair, count in even_odd.most_common()
    ]

    layout = _layout_distribution(spec, all_numbers)
    special = _special_distribution(key, ordered_draws)
    latest = ordered_draws[0] if ordered_draws else None
    previous_repeats = len(set(all_numbers[0]) & set(all_numbers[1])) if len(all_numbers) > 1 else 0
    cycle = _cycle_progress(pool, all_numbers)
    total_appearances = sum(counts.values()) or 1
    pareto_target = total_appearances * 0.8
    pareto_numbers = []
    cumulative = 0
    for row in frequency:
        if cumulative >= pareto_target:
            break
        pareto_numbers.append(row["number"])
        cumulative += row["count"]

    tables = {
        "analysis": {"title": "Análise dos Números", "rows": frequency[:25]},
        "behavior": {"title": "Comportamento das Dezenas", "rows": frequency},
        "cycles": {"title": "Ciclo das Dezenas", "data": cycle},
        "frequency": {"title": "Frequência dos Números mais Sorteados", "rows": frequency},
        "delays": {"title": "Sequências e Atrasos", "rows": gaps},
        "parity": {"title": "Pares e Ímpares", "rows": parity_rows},
        "repeats": {"title": "Repetidas do Concurso Anterior", "data": {"latest_repeats": previous_repeats, "history": repeated}},
        "primes": {"title": "Números Primos", "data": {"prime_numbers": primes, "prime_appearances": prime_hits}},
        "sums": {"title": "Somas dos Números", "data": sum_summary},
        "fibonacci": {"title": "Números de Fibonacci", "data": {"numbers": fibonacci, "appearances": fibonacci_hits}},
        "multiples3": {"title": "Números Múltiplos de Três", "data": {"numbers": [n for n in pool if n % 3 == 0], "appearances": multiple3_hits}},
        "order": {"title": "Ordem de Sorteio e Posição Detalhada", "rows": [{"contest": d.get("contest"), "ordered_numbers": d.get("ordered_numbers", d.get("numbers", []))} for d in ordered_draws[:30]]},
        "pareto": {"title": "Princípio de Pareto", "data": {"top_numbers_for_80_percent_of_hits": pareto_numbers, "total_appearances": total_appearances}},
        "lines-columns": {"title": "Dezenas por Linhas e Colunas", "data": layout},
        "frame-center": {"title": "Dezenas na Moldura e Centro", "data": layout.get("frame_center", {})},
        "missing": {"title": "Dezenas Ausentes", "data": {"numbers_not_seen_in_period": missing}},
        "duos": {"title": "Duques (duplas) mais frequentes", "rows": pairs},
        "trios": {"title": "Trincas mais frequentes", "rows": triples},
        "patterns": {"title": "Padrões", "data": {"consecutive_runs": [{"length": length, "count": count} for length, count in sorted(consecutive.items())], "sum": sum_summary, "parity": parity_rows}},
        "colors": {"title": "Cores das Bolas Sorteadas", "data": {"note": "A referência apresenta esta tabela; a reprodução calcula faixas numéricas, pois a classificação cromática proprietária não foi especificada nas páginas públicas."}},
        "sequence-jumps": {"title": "Sequências e Saltos das Dezenas", "data": {"consecutive_runs": [{"length": length, "count": count} for length, count in sorted(consecutive.items())]}},
        "binary": {"title": "Tabela Binária", "data": {"latest_contest": latest.get("contest") if latest else None, "bitstring": _binary_string(pool, latest.get("numbers", []) if latest else [])}},
        "filters": {"title": "Tabela dos Filtros", "data": {"sum": sum_summary, "parity_distribution": parity_rows, "unique_draws": n_draws}},
    }
    for stat in spec.get("extra_stats", []):
        stat_id, stat_label = stat
        if stat_id == "quadrants":
            tables[stat_id] = {"title": stat_label, "data": _quadrant_distribution(spec, all_numbers)}
        elif stat_id == "second-draw":
            second_rows = [d.get("second_numbers", []) for d in ordered_draws if d.get("second_numbers")]
            second_counts = Counter(n for row in second_rows for n in row)
            tables[stat_id] = {"title": stat_label, "data": {"draws_analyzed": len(second_rows), "frequency": [{"number": n, "count": second_counts[n]} for n in sorted(second_counts)], "most_frequent": [{"number": n, "count": c} for n, c in second_counts.most_common(15)], "note": "Calculada separadamente a partir das dezenas do segundo sorteio oficial."}}
        elif stat_id in {"independencia", "special-draw", "quina-sao-joao", "easter"}:
            marked = [d for d in ordered_draws if d.get("special_draw")]
            tables[stat_id] = {"title": stat_label, "data": {"officially_marked_special_draws": len(marked), "contests": [d.get("contest") for d in marked], "note": "Usa o indicador público de concurso especial retornado pela CAIXA; a classificação por evento pode variar."}}
        elif stat_id in {"final-zero", "final-five"}:
            divisor = 10 if stat_id == "final-zero" else 5
            selected = [d for d in ordered_draws if int(d.get("contest", 0)) % divisor == 0]
            selected_counts = Counter(n for d in selected for n in d.get("numbers", []))
            tables[stat_id] = {"title": stat_label, "data": {"contests_analyzed": len(selected), "contests": [d.get("contest") for d in selected], "most_frequent_numbers": [{"number": n, "count": c} for n, c in selected_counts.most_common(20)]}}
        elif stat_id == "suits":
            band_count = 4
            bands = [Counter() for _ in range(band_count)]
            for row in all_numbers:
                for number in row:
                    bands[(number - low) * band_count // max(high - low + 1, 1)]["hits"] += 1
            tables[stat_id] = {"title": stat_label, "data": {"numeric_bands": [{"band": i + 1, "hits": bands[i]["hits"]} for i in range(band_count)], "note": "As páginas públicas não especificam a regra proprietária de naipes; são exibidas faixas numéricas equilibradas."}}
        elif stat_id in {"months", "months-repeat"}:
            tables[stat_id] = {"title": stat_label, "data": special.get("months", {})}
        elif stat_id == "teams":
            tables[stat_id] = {"title": stat_label, "data": special.get("teams", {})}
        elif stat_id == "team-delays":
            tables[stat_id] = {"title": stat_label, "data": special.get("team_gaps", {})}
        elif stat_id in {"trevos", "trevo-pairs"}:
            tables[stat_id] = {"title": stat_label, "data": special.get("trevos", {})}
        elif stat_id == "trevo-order":
            tables[stat_id] = {"title": stat_label, "data": special.get("trevo_order", {})}
        elif stat_id == "column-frequency":
            tables[stat_id] = {"title": stat_label, "data": special.get("columns", {})}
        elif stat_id == "column-cycles":
            tables[stat_id] = {"title": stat_label, "data": {"per_column": special.get("columns", []), "note": "Ciclo medido no período carregado; consulte a frequência/gap de cada dígito por coluna."}}
        else:
            tables[stat_id] = {"title": stat_label, "data": {"description": "Recorte por modalidade calculado a partir do histórico selecionado.", "recent_contests": [d.get("contest") for d in ordered_draws[:20]]}}

    return {
        "game": key,
        "game_name": spec["name"],
        "draws_analyzed": n_draws,
        "latest_contest": latest.get("contest") if latest else None,
        "frequency": frequency,
        "gaps": gaps,
        "sum": sum_summary,
        "parity_distribution": parity_rows,
        "repeated_from_previous": previous_repeats,
        "pairs": pairs,
        "triples": triples,
        "prime_numbers": primes,
        "fibonacci_numbers": fibonacci,
        "missing_numbers": missing,
        "special": special,
        "layout": layout,
        "tables": tables,
        "statistics_catalog": get_stats(spec),
        "disclaimer": "Frequências e atrasos descrevem apenas o histórico informado. Eles não aumentam nem preveem a probabilidade matemática de um resultado futuro.",
    }


def _layout_distribution(spec: dict, rows: list[list[int]]) -> dict:
    low, high = spec["minimum"], spec["maximum"]
    if spec["key"] == "supersete":
        return {"by_column": _column_frequency(rows)}
    width = 5 if spec["key"] in {"lotofacil", "diadesorte"} else 10
    counts = Counter()
    frame = center = 0
    for row in rows:
        for n in row:
            index = n - low
            row_number, col_number = divmod(index, width)
            counts[f"Linha {row_number + 1}"] += 1
            counts[f"Coluna {col_number + 1}"] += 1
            if spec["key"] in {"lotofacil", "diadesorte"}:
                if row_number in {0, 4} or col_number in {0, 4}:
                    frame += 1
                else:
                    center += 1
    return {"grid_width": width, "counts": dict(counts), "frame_center": {"frame": frame, "center": center}}


def _column_frequency(rows: list[list[int]]) -> list[dict]:
    results = []
    for index in range(7):
        counts = Counter(row[index] for row in rows if len(row) > index)
        recent = [row[index] for row in rows if len(row) > index]
        digits = []
        for number in range(10):
            gap = next((i for i, value in enumerate(recent) if value == number), len(recent))
            digits.append({"digit": number, "count": counts[number], "draws_since_hit": gap})
        results.append({"column": index + 1, "digits": digits})
    return results


def _special_distribution(key: str, draws: list[dict]) -> dict:
    months = Counter()
    teams = Counter()
    trevos = Counter()
    trevo_pairs = Counter()
    trevo_orders = Counter()
    for draw in draws:
        month = draw.get("month")
        if month:
            months[month.get("name") or str(month.get("number"))] += 1
        if draw.get("team"):
            teams[draw["team"]] += 1
        values = draw.get("trevos", [])
        trevos.update(values)
        if len(values) >= 2:
            trevo_pairs.update([tuple(sorted(values[:2]))])
            ordered = draw.get("ordered_numbers", [])
            ordered_trevos = ordered[-2:] if len(ordered) >= 8 else values[:2]
            trevo_orders.update([tuple(ordered_trevos)])
    result = {}
    if key == "diadesorte":
        result["months"] = {"counts": [{"month": name, "count": count} for name, count in months.most_common()], "distinct": len(months)}
    if key == "timemania":
        gaps = []
        team_names = set(teams)
        for team in team_names:
            gap = next((i for i, draw in enumerate(draws) if draw.get("team") == team), len(draws))
            gaps.append({"team": team, "draws_since_hit": gap, "count": teams[team]})
        result["teams"] = {"counts": [{"team": name, "count": count} for name, count in teams.most_common(20)], "distinct": len(teams)}
        result["team_gaps"] = {"items": sorted(gaps, key=lambda row: (-row["draws_since_hit"], row["team"]))[:20]}
    if key == "maismilionaria":
        result["trevos"] = {"counts": [{"trevo": n, "count": trevos[n]} for n in range(1, 7)], "pairs": [{"trevos": list(pair), "count": count} for pair, count in trevo_pairs.most_common()]}
        result["trevo_order"] = {"orders": [{"first": order[0], "second": order[1], "count": count} for order, count in trevo_orders.most_common()], "note": "Ordem extraída da sequência oficial quando os oito valores são informados."}
    if key == "supersete":
        result["columns"] = _column_frequency([d.get("numbers", []) for d in draws])
    return result


def _cycle_progress(pool: list[int], rows: list[list[int]]) -> dict:
    seen = set()
    length = 0
    for row in rows:
        seen.update(row)
        length += 1
        if set(pool).issubset(seen):
            return {"draws_in_current_cycle": length, "coverage_percent": 100.0, "completed": True}
    return {"draws_in_current_cycle": length, "coverage_percent": round(len(seen) * 100 / max(len(pool), 1), 2), "completed": False}


def _quadrant_distribution(spec: dict, rows: list[list[int]]) -> dict:
    low, high = spec["minimum"], spec["maximum"]
    width = 10
    total_rows = (high - low + width) // width
    row_mid = max(1, (total_rows + 1) // 2)
    counts = Counter()
    for values in rows:
        for number in values:
            row, column = divmod(number - low, width)
            quadrant = (1 if row < row_mid else 3) + (0 if column < width / 2 else 1)
            counts[f"Q{quadrant}"] += 1
    return {"grid_width": width, "draws_analyzed": len(rows), "counts": {f"Q{i}": counts[f"Q{i}"] for i in range(1, 5)}, "note": "Divisão calculada sobre uma grade numérica de dez colunas."}


def _binary_string(pool: list[int], drawn: list[int]) -> str:
    drawn_set = set(drawn)
    return "".join("1" if n in drawn_set else "0" for n in pool)
