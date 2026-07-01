"""
RetailPro — подготовка плоской таблицы для Power BI.

Колонки источника: date, region, category, manager, revenue,
quantity, discount_amount, status, returns.

Запуск:
    python prepare_retailpro_data.py --input sales.csv --output retailpro_sales.csv
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from role_access import build_user_access, export_role_datasets

COLUMNS = [
    "date", "region", "category", "manager", "revenue",
    "quantity", "discount_amount", "status", "returns",
]
RETURN_STATUS = {"return", "cancel", "cancelled", "canceled", "возврат", "отмена"}


def load_data(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
    else:
        df = pd.read_excel(path)
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Нет колонок: {sorted(missing)}")
    return df


def prepare_for_powerbi(df: pd.DataFrame, months: int = 3) -> pd.DataFrame:
    """Загрузка, очистка, фильтр последних 3 месяцев, производные поля."""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["region"] = out["region"].astype(str).str.strip()
    out["category"] = out["category"].astype(str).str.strip()
    out["manager"] = out["manager"].astype(str).str.strip()
    out["status"] = out["status"].astype(str).str.strip().str.lower()
    out["revenue"] = pd.to_numeric(out["revenue"], errors="coerce").fillna(0)
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce").fillna(0)
    out["discount_amount"] = pd.to_numeric(out["discount_amount"], errors="coerce").fillna(0)
    out["returns"] = pd.to_numeric(out["returns"], errors="coerce").fillna(0).astype(int)
    out = out.dropna(subset=["date"])

    # П.1 требования: последние 3 месяца от текущей даты
    today = pd.Timestamp(date.today())
    start = (today - pd.DateOffset(months=months)).replace(day=1)
    out = out[(out["date"] >= start) & (out["date"] <= today)].copy()

    # Производные поля для визуализаций и прозрачных расчётов
    out["week_start"] = out["date"] - pd.to_timedelta(out["date"].dt.weekday, unit="D")
    out["is_return_or_cancel"] = (
        (out["returns"] > 0) | out["status"].isin(RETURN_STATUS)
    ).astype(int)
    out["is_application"] = 1
    out["is_sale"] = (
        (out["revenue"] > 0)
        & (out["returns"] == 0)
        & (~out["status"].isin(RETURN_STATUS))
    ).astype(int)

    return out.reset_index(drop=True)


def calc_metrics(df: pd.DataFrame) -> dict:
    """
    Базовые метрики для проверки (1 строка = 1 транзакция).
    Основные KPI на дашборде считаются в Power BI (DAX).
    """
    if df.empty:
        return {}

    total_revenue = df["revenue"].sum()
    applications_count = len(df)
    sales_count = int(df["is_sale"].sum())
    sales_revenue = df.loc[df["is_sale"] == 1, "revenue"].sum()
    conversion_pct = sales_count / applications_count * 100 if applications_count else 0
    avg_check = sales_revenue / sales_count if sales_count else 0
    returns_count = int(df["is_return_or_cancel"].sum())
    returns_pct = returns_count / applications_count * 100 if applications_count else 0

    cat_rev = df.groupby("category")["revenue"].sum().nlargest(5).sum()
    top5_share = cat_rev / total_revenue * 100 if total_revenue else 0

    reg = df.groupby("region")["revenue"].sum()
    region_share = (reg / reg.sum() * 100).to_dict() if reg.sum() else {}

    # MoM: последний месяц в данных vs предыдущий
    last_month = df["date"].max().to_period("M")
    cur = df[df["date"].dt.to_period("M") == last_month]
    prev = df[df["date"].dt.to_period("M") == last_month - 1]
    rev_cur, rev_prev = cur["revenue"].sum(), prev["revenue"].sum()
    mom = (rev_cur - rev_prev) / rev_prev * 100 if rev_prev else None

    return {
        "total_revenue": total_revenue,
        "applications_count": applications_count,
        "sales_count": sales_count,
        "conversion_pct": conversion_pct,
        "average_check": avg_check,
        "transactions_count": applications_count,
        "returns_count": returns_count,
        "returns_pct": returns_pct,
        "top5_categories_share_pct": top5_share,
        "region_share_pct": region_share,
        "revenue_mom_pct": mom,
    }


def detail_table(df: pd.DataFrame) -> pd.DataFrame:
    """П.5: таблица детализации."""
    return df[["date", "region", "category", "revenue", "manager"]].sort_values("date")


def export_excel(df: pd.DataFrame, path: Path) -> None:
    """П.7: выгрузка детализации в Excel."""
    detail_table(df).to_excel(path, index=False, sheet_name="Detail")


def build_calendar(df: pd.DataFrame) -> pd.DataFrame:
    dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    cal = pd.DataFrame({"Date": dates})
    cal["Year"] = cal["Date"].dt.year
    cal["Month"] = cal["Date"].dt.month
    cal["YearMonth"] = cal["Date"].dt.to_period("M").astype(str)
    return cal


def export_powerbi_package(df: pd.DataFrame, out_dir: Path, raw: pd.DataFrame | None = None) -> None:
    """Выгрузка набора файлов для Power BI."""
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "retailpro_sales.csv", index=False, encoding="utf-8-sig")
    build_calendar(df).to_csv(out_dir / "Calendar.csv", index=False, encoding="utf-8-sig")
    detail_table(df).to_csv(out_dir / "Detail.csv", index=False, encoding="utf-8-sig")
    detail_table(df).to_excel(out_dir / "retailpro_detail.xlsx", index=False, sheet_name="Detail")
    build_user_access(df).to_csv(out_dir / "UserAccess.csv", index=False, encoding="utf-8-sig")
    export_role_datasets(df, out_dir)

    from generate_acceptance_report import export_package

    export_package(df, raw if raw is not None else df, out_dir.parent / "acceptance_package")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", default="retailpro_sales.csv")
    p.add_argument("--excel", default="retailpro_detail.xlsx")
    p.add_argument("--powerbi-dir", default="powerbi_data", help="Папка для Power BI")
    args = p.parse_args()

    raw = load_data(Path(args.input))
    df = prepare_for_powerbi(raw)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    export_excel(df, Path(args.excel))
    export_powerbi_package(df, Path(args.powerbi_dir), raw=raw)

    print(f"Строк: {len(df)}")
    print(f"Период: {df['date'].min().date()} — {df['date'].max().date()}")
    print(f"CSV: {args.output}")
    print(f"Excel: {args.excel}")
    print(f"Power BI: {Path(args.powerbi_dir).resolve()}")
    print("Метрики (проверка):", calc_metrics(df))


if __name__ == "__main__":
    main()
