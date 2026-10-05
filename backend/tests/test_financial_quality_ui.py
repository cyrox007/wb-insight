from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_overview_marks_incomplete_profit_explicitly():
    source = _read("frontend/src/pages/Dashboard/Main/index.vue")

    assert "stats.profit?.complete === false" in source
    assert "Прибыль рассчитана не полностью." in source
    assert "cost_coverage_percent" in source
    assert "missing_cost_operations" in source


def test_unit_economy_marks_incomplete_profit_explicitly():
    source = _read("frontend/src/pages/Dashboard/UnityEconomy/index.vue")

    assert "unityData?.profit_complete === false" in source
    assert "Прибыль рассчитана не полностью." in source
    assert "cost_coverage_percent" in source
    assert "cost_missing_operations" in source
