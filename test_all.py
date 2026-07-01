"""Полная проверка проекта RetailPro."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

from prepare_retailpro_data import (
    COLUMNS,
    calc_metrics,
    detail_table,
    export_powerbi_package,
    load_data,
    prepare_for_powerbi,
)

ROOT = Path(__file__).parent
errors: list[str] = []
checks: list[str] = []


def ok(msg: str) -> None:
    checks.append(f"OK  {msg}")


def fail(msg: str) -> None:
    errors.append(f"FAIL {msg}")


def main() -> int:
    sales = ROOT / "sales.csv"
    if not sales.exists():
        fail("sales.csv отсутствует")
        return 1

    # 1. Колонки источника
    raw = load_data(sales)
    if list(raw.columns) != COLUMNS and set(COLUMNS) - set(raw.columns):
        fail("Неверные колонки в sales.csv")
    else:
        ok(f"Колонки sales.csv: {len(COLUMNS)} шт.")

    # 2. Подготовка данных
    df = prepare_for_powerbi(raw)
    if df.empty:
        fail("После фильтра 3 мес. данных нет")
    else:
        ok(f"Строк после фильтра: {len(df)}")

    today = pd.Timestamp(date.today())
    start = (today - pd.DateOffset(months=3)).replace(day=1)
    if df["date"].min() < start or df["date"].max() > today:
        fail(f"Даты вне диапазона 3 мес.: {df['date'].min()} — {df['date'].max()}")
    else:
        ok(f"Период: {df['date'].min().date()} — {df['date'].max().date()}")

    required_derived = {"week_start", "is_return_or_cancel"}
    if not required_derived.issubset(df.columns):
        fail(f"Нет полей: {required_derived - set(df.columns)}")
    else:
        ok("Производные поля week_start, is_return_or_cancel")

    # 3. Метрики — сверка с ручным расчётом
    m = calc_metrics(df)
    manual_rev = float(df["revenue"].sum())
    manual_tx = len(df)
    manual_avg = manual_rev / manual_tx
    manual_ret = int(df["is_return_or_cancel"].sum())

    if abs(m["total_revenue"] - manual_rev) > 0.01:
        fail(f"Выручка: {m['total_revenue']} != {manual_rev}")
    else:
        ok(f"Выручка: {manual_rev:,.0f}")

    if m["transactions_count"] != manual_tx:
        fail("Транзакции не совпадают")
    else:
        ok(f"Транзакции: {manual_tx}")

    if abs(m["average_check"] - manual_avg) > 0.01:
        fail("Средний чек не совпадает")
    else:
        ok(f"Средний чек: {manual_avg:,.0f}")

    if m["returns_count"] != manual_ret:
        fail("Возвраты не совпадают")
    else:
        ok(f"Возвраты: {manual_ret} ({m['returns_pct']:.1f}%)")

    top5 = df.groupby("category")["revenue"].sum().nlargest(5).sum()
    top5_pct = top5 / manual_rev * 100
    if abs(m["top5_categories_share_pct"] - top5_pct) > 0.01:
        fail("Доля топ-5 не совпадает")
    else:
        ok(f"Топ-5 категорий: {top5_pct:.1f}%")

    reg_sum = sum(m["region_share_pct"].values())
    if abs(reg_sum - 100) > 0.1:
        fail(f"Доли регионов != 100%: {reg_sum}")
    else:
        ok(f"Доли регионов в сумме: {reg_sum:.1f}%")

    # 4. Детализация
    det = detail_table(df)
    expected_cols = ["date", "region", "category", "revenue", "manager"]
    if list(det.columns) != expected_cols:
        fail(f"Детализация: {list(det.columns)}")
    else:
        ok("Таблица детализации: 5 колонок")

    # 5. Power BI export
    pbi_dir = ROOT / "_test_powerbi"
    export_powerbi_package(df, pbi_dir)
    for name in ("retailpro_sales.csv", "Calendar.csv", "Detail.csv", "retailpro_detail.xlsx"):
        p = pbi_dir / name
        if not p.exists() or p.stat().st_size == 0:
            fail(f"Не создан {name}")
        else:
            ok(f"powerbi_data/{name}")

    cal = pd.read_csv(pbi_dir / "Calendar.csv")
    if "Date" not in cal.columns:
        fail("Calendar без колонки Date")
    else:
        ok(f"Calendar: {len(cal)} дней")

    # 6. DAX файл
    dax = ROOT / "dax_measures.txt"
    required_measures = [
        "Total Revenue", "Transactions Count", "Average Check",
        "Returns Count", "Returns %", "Previous Month Revenue",
        "Revenue MoM Growth %", "Top 5 Categories Share %", "Regions Share %",
    ]
    dax_text = dax.read_text(encoding="utf-8")
    for measure in required_measures:
        if measure not in dax_text:
            fail(f"DAX: нет меры '{measure}'")
        else:
            ok(f"DAX: {measure}")

    # 7. Инструкция Power BI
    guide = ROOT / "power_bi_visuals.txt"
    if not guide.exists():
        fail("power_bi_visuals.txt отсутствует")
    else:
        ok("power_bi_visuals.txt")

    # 8. Dashboard import
    try:
        import dashboard  # noqa: F401
        ok("dashboard.py импортируется")
    except Exception as e:
        fail(f"dashboard.py: {e}")

    # 9. Power BI PBIP project
    pbip = ROOT / "RetailPro" / "RetailPro.pbip"
    if not pbip.exists():
        fail("RetailPro.pbip не найден — запустите: python build_powerbi_project.py")
    else:
        ok(f"RetailPro.pbip ({pbip.stat().st_size} bytes)")
        visuals = list((ROOT / "RetailPro" / "RetailPro.Report").rglob("visual.json"))
        if len(visuals) < 10:
            fail(f"Мало визуалов в PBIP: {len(visuals)}")
        else:
            ok(f"Визуалов в отчёте: {len(visuals)}")
        for tmdl in ("retailpro_sales.tmdl", "Calendar.tmdl", "_Measures.tmdl"):
            p = ROOT / "RetailPro" / "RetailPro.SemanticModel" / "definition" / "tables" / tmdl
            if not p.exists():
                fail(f"Нет {tmdl}")
            else:
                ok(f"TMDL: {tmdl}")

    print("\n".join(checks))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"\nВсе проверки пройдены: {len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
