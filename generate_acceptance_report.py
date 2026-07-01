"""
Генерация пакета документов для приёмки заказчиком.

Запуск:
    python generate_acceptance_report.py --input sales.csv
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from prepare_retailpro_data import (
    calc_metrics,
    load_data,
    prepare_for_powerbi,
)
from role_access import build_insights_text


def build_data_preparation_doc(df_raw: pd.DataFrame, df: pd.DataFrame) -> str:
    today = date.today()
    return f"""================================================================================
RETAILPRO — ОЧИСТКА И ПОДГОТОВКА ДАННЫХ
================================================================================
Дата отчёта: {today.isoformat()}

1. ИСХОДНЫЕ ДАННЫЕ
------------------
Строк загружено:        {len(df_raw):,}
Строк после подготовки: {len(df):,}
Период в отчёте:        {df['date'].min().date()} — {df['date'].max().date()}
Ограничение:            последние 3 месяца от {today.isoformat()}

Колонки источника (без добавления вымышленных полей):
  date, region, category, manager, revenue, quantity,
  discount_amount, status, returns

2. ШАГИ ОЧИСТКИ (prepare_retailpro_data.py)
-------------------------------------------
[1] date          → datetime, некорректные даты удалены
[2] region        → trim, строка
[3] category      → trim, строка (продукт/категория)
[4] manager       → trim, строка
[5] status        → lower case
[6] revenue       → numeric >= 0
[7] quantity      → numeric
[8] discount_amount → numeric
[9] returns       → integer
[10] Фильтр периода: date >= начало (today - 3 мес.) AND date <= today

3. ПРОИЗВОДНЫЕ ПОЛЯ (прозрачные правила)
----------------------------------------
week_start          — понедельник недели для графика динамики
is_return_or_cancel — returns > 0 ИЛИ status in {{return, cancel, ...}}
is_application      — 1 для каждой строки (заявка/обращение)
is_sale             — продажа: revenue > 0, returns = 0, status не отмена/возврат

4. СООТВЕТСТВИЕ ФИЛЬТРОВ ДАШБОРДА
---------------------------------
Период              → date / Calendar[Date]     — ДА
Источник/канал      → region (регион продаж)    — ДА*
Продукт/услуга      → category                — ДА
Менеджер            → manager                 — ДА
Регион/сегмент      → region                  — ДА

* Отдельной колонки source в источнике нет; region используется
  как канал географических продаж (согласовано с моделью RetailPro).

5. ВЫХОДНЫЕ ФАЙЛЫ
-----------------
powerbi_data/retailpro_sales.csv
powerbi_data/Calendar.csv
powerbi_data/Detail.csv
powerbi_data/UserAccess.csv
powerbi_data/by_role/...

================================================================================
"""


def build_kpi_verification(df: pd.DataFrame) -> str:
    m = calc_metrics(df)
    manual_apps = len(df)
    manual_sales = int(df["is_sale"].sum())
    manual_rev = float(df["revenue"].sum())
    manual_sales_rev = float(df.loc[df["is_sale"] == 1, "revenue"].sum())
    manual_conv = manual_sales / manual_apps * 100 if manual_apps else 0
    manual_avg = manual_sales_rev / manual_sales if manual_sales else 0

    lines = [
        "=" * 80,
        "RETAILPRO — ПРОВЕРКА KPI (СВЕРКА С PANDAS)",
        "=" * 80,
        "",
        "| KPI | Формула | Значение | Статус |",
        "|-----|---------|----------|--------|",
    ]

    checks = [
        ("Выручка", "SUM(revenue)", m["total_revenue"], manual_rev),
        ("Заявки", "COUNT(rows)", m["applications_count"], manual_apps),
        ("Продажи", "SUM(is_sale=1)", m["sales_count"], manual_sales),
        ("Конверсия %", "Продажи/Заявки*100", m["conversion_pct"], manual_conv),
        ("Средний чек", "SUM(revenue продаж)/Продажи", m["average_check"], manual_avg),
        ("Возвраты шт.", "SUM(is_return_or_cancel)", m["returns_count"], int(df["is_return_or_cancel"].sum())),
        ("Возвраты %", "Возвраты/Заявки*100", m["returns_pct"], df["is_return_or_cancel"].sum() / len(df) * 100),
    ]

    all_ok = True
    for name, formula, calc_val, manual_val in checks:
        ok = abs(float(calc_val) - float(manual_val)) < 0.02 if calc_val is not None else False
        if not ok:
            all_ok = False
        status = "OK" if ok else "РАСХОЖДЕНИЕ"
        lines.append(f"| {name} | {formula} | {calc_val:,.2f} | {status} |")

    lines.extend([
        "",
        f"Итог сверки: {'ВСЕ KPI СОВПАДАЮТ' if all_ok else 'ЕСТЬ РАСХОЖДЕНИЯ'}",
        "",
        "Детализация по статусам:",
    ])
    for status, cnt in df["status"].value_counts().items():
        lines.append(f"  {status}: {cnt}")
    lines.append("")
    return "\n".join(lines)


def build_filters_and_charts_doc() -> str:
    return """================================================================================
RETAILPRO — ФИЛЬТРЫ И ГРАФИКИ (ПОДТВЕРЖДЕНИЕ ПОЛНОТЫ)
================================================================================

ФИЛЬТРЫ НА ДАШБОРДЕ
-------------------
| Фильтр           | Поле      | Менеджер | Руководитель | Директор |
|------------------|-----------|----------|--------------|----------|
| Период           | date      |    +     |      +       |    +     |
| Источник (регион)| region    |    —     |      —       |    +     |
| Продукт/категория| category  |    +     |      +       |    +     |
| Менеджер         | manager   |    —*    |      +       |    +     |
| Регион/сегмент   | region    |    —     |      —       |    +     |

* Менеджер видит только свои данные (RLS), отдельный срез не нужен.

ГРАФИКИ
-------
| График                         | Тип              | Страница   |
|--------------------------------|------------------|------------|
| Динамика выручки по неделям    | Линейный + тренд | Все роли   |
| Сравнение каналов (регионов)   | Горизонт. столб. | Директор   |
| Распределение по менеджерам    | Горизонт. столб. | Руководитель|
| Распределение по продуктам     | Топ-5 категорий  | Все роли   |

KPI-КАРТОЧКИ
------------
Выручка | Заявки | Продажи | Конверсия | Средний чек | Возвраты
(+ динамика MoM для выручки, заявок, среднего чека)

БЛОК УПРАВЛЕНЧЕСКИХ ВЫВОДОВ
---------------------------
3 автоматических текста на каждой странице отчёта (меры Insight*).

================================================================================
"""


def build_management_summary(insights: list[str]) -> str:
    body = "\n".join(f"  {i}. {t}" for i, t in enumerate(insights, 1))
    return f"""================================================================================
RETAILPRO — УПРАВЛЕНЧЕСКОЕ РЕЗЮМЕ (2–3 НАБЛЮДЕНИЯ)
================================================================================

{body}

Логика формирования:
  1) Лидер по выручке среди регионов (доля %)
  2) Динамика среднего чека к предыдущему месяцу
  3) Конверсия заявок в продажи vs целевой ориентир 60%
  (альтернатива: возвраты vs целевой уровень 5%)

Выводы пересчитываются при любом фильтре на дашборде.

================================================================================
"""


def export_package(df: pd.DataFrame, df_raw: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    insights = build_insights_text(df)

    (out_dir / "01_ПОДГОТОВКА_ДАННЫХ.txt").write_text(
        build_data_preparation_doc(df_raw, df), encoding="utf-8"
    )
    (out_dir / "02_ПРОВЕРКА_KPI.txt").write_text(build_kpi_verification(df), encoding="utf-8")
    (out_dir / "03_ФИЛЬТРЫ_И_ГРАФИКИ.txt").write_text(build_filters_and_charts_doc(), encoding="utf-8")
    (out_dir / "04_УПРАВЛЕНЧЕСКОЕ_РЕЗЮМЕ.txt").write_text(
        build_management_summary(insights), encoding="utf-8"
    )

    metrics = calc_metrics(df)
    kpi_json = {}
    for k, v in metrics.items():
        if isinstance(v, dict):
            kpi_json[k] = {rk: float(rv) for rk, rv in v.items()}
        elif v is None:
            kpi_json[k] = None
        else:
            kpi_json[k] = float(v)

    summary = {
        "generated": date.today().isoformat(),
        "rows": len(df),
        "period": {"from": str(df["date"].min().date()), "to": str(df["date"].max().date())},
        "kpi": kpi_json,
        "insights": insights,
        "filters": ["period", "region_as_source", "category", "manager", "region_segment"],
        "charts": ["weekly_dynamics", "region_channels", "manager_distribution", "product_top5"],
    }
    (out_dir / "acceptance_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    combined = "\n\n".join([
        build_data_preparation_doc(df_raw, df),
        build_kpi_verification(df),
        build_filters_and_charts_doc(),
        build_management_summary(insights),
    ])
    (out_dir / "ПАКЕТ_ПРИЕМКИ.txt").write_text(combined, encoding="utf-8")
    print(f"Пакет приёмки: {out_dir.resolve()}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="sales.csv")
    p.add_argument("--output", default="acceptance_package")
    args = p.parse_args()

    raw = load_data(Path(args.input))
    df = prepare_for_powerbi(raw)
    export_package(df, raw, Path(args.output))


if __name__ == "__main__":
    main()
