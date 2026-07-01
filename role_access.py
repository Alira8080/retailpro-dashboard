"""
Роли доступа: менеджер, руководитель, коммерческий директор.

Менеджер      — только свои продажи
Руководитель  — продажи своего региона (все менеджеры региона)
Ком. директор — все данные компании
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROLE_MANAGER = "Менеджер"
ROLE_SUPERVISOR = "Руководитель"
ROLE_DIRECTOR = "Коммерческий директор"
CONVERSION_TARGET = 60.0


def build_insights_text(df: "pd.DataFrame") -> list[str]:
    """2–3 управленческих наблюдения для пакета приёмки и дашборда."""
    import pandas as pd

    if df.empty:
        return ["Нет данных за выбранный период."]

    insights: list[str] = []
    reg = df.groupby("region")["revenue"].sum().sort_values(ascending=False)
    if reg.sum() > 0:
        share = reg.iloc[0] / reg.sum() * 100
        insights.append(
            f"Регион «{reg.index[0]}» — основной канал продаж ({share:.1f}% выручки); "
            f"имеет смысл усилить присутствие в отстающих регионах."
        )

    last = df["date"].max().to_period("M")
    cur = df[df["date"].dt.to_period("M") == last]
    prev = df[df["date"].dt.to_period("M") == last - 1]
    if len(cur) and len(prev):
        avg_cur = cur.loc[cur["is_sale"] == 1, "revenue"].sum() / max(cur["is_sale"].sum(), 1)
        avg_prev = prev.loc[prev["is_sale"] == 1, "revenue"].sum() / max(prev["is_sale"].sum(), 1)
        if avg_prev:
            pct = (avg_cur - avg_prev) / avg_prev * 100
            word = "вырос" if pct >= 0 else "снизился"
            insights.append(
                f"Средний чек {word} на {abs(pct):.1f}% к пред. месяцу — "
                f"{'позитивная' if pct >= 0 else 'негативная'} динамика для маржинальности."
            )

    conv = df["is_sale"].sum() / len(df) * 100 if len(df) else 0
    if conv >= CONVERSION_TARGET:
        insights.append(
            f"Конверсия заявок в продажи ({conv:.1f}%) на уровне или выше ориентира ({CONVERSION_TARGET:.0f}%)."
        )
    else:
        insights.append(
            f"Конверсия ({conv:.1f}%) ниже ориентира {CONVERSION_TARGET:.0f}% — "
            f"рекомендуется разбор отмен и возвратов по менеджерам."
        )

    return insights[:3]


def build_detailed_insights(df: "pd.DataFrame") -> list[str]:
    """Развёрнутые управленческие наблюдения (2–3 абзаца) для заказчика."""
    if df.empty:
        return ["Нет данных за выбранный период для формирования выводов."]

    from prepare_retailpro_data import calc_metrics

    m = calc_metrics(df)
    observations: list[str] = []

    reg = df.groupby("region")["revenue"].sum().sort_values(ascending=False)
    if reg.sum() > 0:
        leader = reg.index[0]
        laggard = reg.index[-1]
        leader_rev = float(reg.iloc[0])
        laggard_rev = float(reg.iloc[-1])
        total_rev = float(reg.sum())
        leader_share = leader_rev / total_rev * 100
        laggard_share = laggard_rev / total_rev * 100
        observations.append(
            f"НАБЛЮДЕНИЕ 1. Структура продаж по каналам (регионам)\n\n"
            f"Регион «{leader}» — ведущий канал: {leader_share:.1f}% выручки "
            f"({leader_rev:,.0f} ₽ из {total_rev:,.0f} ₽ за период). "
            f"Наименее результативный регион — «{laggard}» ({laggard_share:.1f}%). "
            f"Концентрация спроса в одном регионе создаёт зависимость от локального рынка. "
            f"Рекомендация: усилить продвижение и работу с партнёрами в отстающих регионах, "
            f"чтобы сбалансировать географию продаж."
        )

    last = df["date"].max().to_period("M")
    cur = df[df["date"].dt.to_period("M") == last]
    prev = df[df["date"].dt.to_period("M") == last - 1]
    if len(cur) and len(prev):
        avg_cur = cur.loc[cur["is_sale"] == 1, "revenue"].sum() / max(cur["is_sale"].sum(), 1)
        avg_prev = prev.loc[prev["is_sale"] == 1, "revenue"].sum() / max(prev["is_sale"].sum(), 1)
        if avg_prev:
            pct = (avg_cur - avg_prev) / avg_prev * 100
            direction = "рост" if pct >= 0 else "снижение"
            observations.append(
                f"НАБЛЮДЕНИЕ 2. Динамика среднего чека\n\n"
                f"Средний чек за последний месяц — {avg_cur:,.0f} ₽ "
                f"({direction} на {abs(pct):.1f}% к предыдущему месяцу, было {avg_prev:,.0f} ₽). "
                f"{'Положительная динамика поддерживает маржинальность и указывает на успешные допродажи или сдвиг в сторону более дорогих категорий.' if pct >= 0 else 'Снижение среднего чека сигнализирует о давлении на цену или росте доли бюджетных позиций — стоит проверить скидочную политику по категориям.'}"
            )

    conv = float(m.get("conversion_pct", 0))
    sales = int(m.get("sales_count", 0))
    apps = int(m.get("applications_count", 0))
    returns_pct = float(m.get("returns_pct", 0))
    if conv >= CONVERSION_TARGET:
        observations.append(
            f"НАБЛЮДЕНИЕ 3. Конверсия заявок в продажи\n\n"
            f"Конверсия составляет {conv:.1f}% ({sales} продаж из {apps} заявок) — "
            f"на уровне или выше целевого ориентира {CONVERSION_TARGET:.0f}%. "
            f"Воронка работает стабильно; приоритет — удержание текущего уровня сервиса и сокращение возвратов ({returns_pct:.1f}%)."
        )
    else:
        observations.append(
            f"НАБЛЮДЕНИЕ 3. Конверсия заявок в продажи\n\n"
            f"Конверсия {conv:.1f}% ({sales} продаж из {apps} заявок) — ниже ориентира {CONVERSION_TARGET:.0f}%. "
            f"Доля возвратов и отмен — {returns_pct:.1f}%. "
            f"Рекомендация: провести разбор отмен по менеджерам и категориям, выявить типовые причины потери сделок "
            f"и скорректировать скрипты продаж в проблемных сегментах."
        )

    return observations[:3]


def build_user_access(df: pd.DataFrame) -> pd.DataFrame:
    """Таблица учётных записей для RLS в Power BI."""
    rows: list[dict] = []

    for manager in sorted(df["manager"].unique()):
        login = f"{manager.lower().replace(' ', '')}@retailpro.local"
        rows.append(
            {
                "user_login": login,
                "role": ROLE_MANAGER,
                "manager": manager,
                "region": "",
            }
        )

    for region in sorted(df["region"].unique()):
        login = f"head.{region.lower().replace(' ', '_')}@retailpro.local"
        rows.append(
            {
                "user_login": login,
                "role": ROLE_SUPERVISOR,
                "manager": "",
                "region": region,
            }
        )

    rows.append(
        {
            "user_login": "director@retailpro.local",
            "role": ROLE_DIRECTOR,
            "manager": "",
            "region": "",
        }
    )

    return pd.DataFrame(rows)


def filter_by_role(df: pd.DataFrame, role: str, manager: str = "", region: str = "") -> pd.DataFrame:
    """Фильтр данных по роли (для выгрузок и веб-дашборда)."""
    if role == ROLE_DIRECTOR:
        return df.copy()
    if role == ROLE_SUPERVISOR:
        if not region:
            raise ValueError("Для руководителя укажите region")
        return df[df["region"] == region].copy()
    if role == ROLE_MANAGER:
        if not manager:
            raise ValueError("Для менеджера укажите manager")
        return df[df["manager"] == manager].copy()
    raise ValueError(f"Неизвестная роль: {role}")


def export_role_datasets(df: pd.DataFrame, out_dir: Path) -> None:
    """Отдельные файлы данных по ролям."""
    base = out_dir / "by_role"
    base.mkdir(parents=True, exist_ok=True)

    detail_cols = ["date", "region", "category", "revenue", "manager"]

    # Коммерческий директор — всё
    director_dir = base / "director"
    director_dir.mkdir(exist_ok=True)
    df.to_csv(director_dir / "sales.csv", index=False, encoding="utf-8-sig")
    df[detail_cols].to_excel(director_dir / "detail.xlsx", index=False, sheet_name="Detail")

    # Руководитель — по регионам
    for region in sorted(df["region"].unique()):
        reg_df = filter_by_role(df, ROLE_SUPERVISOR, region=region)
        reg_dir = base / "supervisor" / region
        reg_dir.mkdir(parents=True, exist_ok=True)
        reg_df.to_csv(reg_dir / "sales.csv", index=False, encoding="utf-8-sig")
        reg_df[detail_cols].to_excel(reg_dir / "detail.xlsx", index=False, sheet_name="Detail")

    # Менеджер — по сотрудникам
    for manager in sorted(df["manager"].unique()):
        mgr_df = filter_by_role(df, ROLE_MANAGER, manager=manager)
        mgr_dir = base / "manager" / manager
        mgr_dir.mkdir(parents=True, exist_ok=True)
        mgr_df.to_csv(mgr_dir / "sales.csv", index=False, encoding="utf-8-sig")
        mgr_df[detail_cols].to_excel(mgr_dir / "detail.xlsx", index=False, sheet_name="Detail")
