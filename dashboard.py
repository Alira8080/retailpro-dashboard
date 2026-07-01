"""
RetailPro MVP Dashboard — открывается в браузере.

Запуск:
    pip install -r requirements.txt
    python generate_sample_data.py   # если нет sales.csv
    streamlit run dashboard.py
"""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from prepare_retailpro_data import calc_metrics, detail_table, prepare_for_powerbi
from role_access import (
    ROLE_DIRECTOR,
    ROLE_MANAGER,
    ROLE_SUPERVISOR,
    build_detailed_insights,
    build_insights_text,
    filter_by_role,
)

DATA_FILE = Path(__file__).parent / "sales.csv"
ROLES = [ROLE_MANAGER, ROLE_SUPERVISOR, ROLE_DIRECTOR]


@st.cache_data
def load_dashboard_data(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        raw = pd.read_csv(p, encoding="utf-8-sig")
    else:
        raw = pd.read_excel(p)
    return prepare_for_powerbi(raw)


def filter_data(df: pd.DataFrame, date_range, regions, categories, managers) -> pd.DataFrame:
    out = df.copy()
    if date_range:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        out = out[(out["date"] >= start) & (out["date"] <= end)]
    if regions:
        out = out[out["region"].isin(regions)]
    if categories:
        out = out[out["category"].isin(categories)]
    if managers:
        out = out[out["manager"].isin(managers)]
    return out


def mom_pct(cur: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return (cur - prev) / prev * 100


def current_vs_prev_month(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df
    last = df["date"].max().to_period("M")
    cur = df[df["date"].dt.to_period("M") == last]
    prev = df[df["date"].dt.to_period("M") == last - 1]
    return cur, prev


def kpi_card(label: str, value: str, delta: float | None) -> None:
    if delta is None:
        st.metric(label, value)
    else:
        st.metric(label, value, f"{delta:+.1f}% к пред. мес.")


def month_kpi(month_df: pd.DataFrame) -> dict[str, float]:
    if month_df.empty:
        return {"revenue": 0, "applications": 0, "sales": 0, "conversion": 0, "avg_check": 0}
    apps = len(month_df)
    sales = int(month_df["is_sale"].sum())
    sales_rev = float(month_df.loc[month_df["is_sale"] == 1, "revenue"].sum())
    return {
        "revenue": float(month_df["revenue"].sum()),
        "applications": apps,
        "sales": sales,
        "conversion": sales / apps * 100 if apps else 0,
        "avg_check": sales_rev / sales if sales else 0,
    }


def main() -> None:
    st.set_page_config(page_title="RetailPro Dashboard", layout="wide")
    st.title("RetailPro — дашборд продаж (электроника)")

    if not DATA_FILE.exists():
        st.error(f"Файл данных не найден: {DATA_FILE}")
        st.code("python generate_sample_data.py", language="bash")
        st.stop()

    df_all = load_dashboard_data(str(DATA_FILE))
    if df_all.empty:
        st.error("После фильтра 3 месяцев данных нет. Проверьте даты в исходном файле.")
        st.stop()

    min_d, max_d = df_all["date"].min().date(), df_all["date"].max().date()
    default_start = max_d - timedelta(days=90)
    if default_start < min_d:
        default_start = min_d

    with st.sidebar:
        st.header("Роль и фильтры")
        role = st.selectbox("Роль", ROLES, index=2)

        managers = sorted(df_all["manager"].unique())
        regions = sorted(df_all["region"].unique())

        selected_manager = ""
        selected_region = ""
        if role == ROLE_MANAGER:
            selected_manager = st.selectbox("Менеджер", managers)
        elif role == ROLE_SUPERVISOR:
            selected_region = st.selectbox("Регион", regions)

        date_range = st.date_input(
            "Период",
            value=(default_start, max_d),
            min_value=min_d,
            max_value=max_d,
        )
        regions_f = st.multiselect("Регион", regions, default=[], disabled=role != ROLE_DIRECTOR)
        categories = st.multiselect("Категория", sorted(df_all["category"].unique()), default=[])
        managers_f = st.multiselect("Менеджер", managers, default=[], disabled=role == ROLE_MANAGER)
        st.caption("Пустой выбор = все значения в рамках роли")
        st.caption("Источник/канал = регион (отдельной колонки source в данных нет)")

    if isinstance(date_range, tuple) and len(date_range) == 2:
        dr = date_range
    else:
        dr = (min_d, max_d)

    df = filter_by_role(df_all, role, manager=selected_manager, region=selected_region)
    df = filter_data(
        df,
        dr,
        regions_f or list(df["region"].unique()),
        categories or list(df_all["category"].unique()),
        managers_f or list(df["manager"].unique()),
    )

    st.info({
        ROLE_MANAGER: f"Режим менеджера: только продажи «{selected_manager}»",
        ROLE_SUPERVISOR: f"Режим руководителя: регион «{selected_region}»",
        ROLE_DIRECTOR: "Режим коммерческого директора: все регионы и менеджеры",
    }[role])

    metrics = calc_metrics(df)
    cur, prev = current_vs_prev_month(df)
    cur_k = month_kpi(cur)
    prev_k = month_kpi(prev)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        kpi_card("Выручка", f"{cur_k['revenue']:,.0f} ₽", mom_pct(cur_k["revenue"], prev_k["revenue"]))
    with c2:
        kpi_card("Заявки", f"{cur_k['applications']:,}", mom_pct(cur_k["applications"], prev_k["applications"]))
    with c3:
        kpi_card("Продажи", f"{cur_k['sales']:,}", mom_pct(cur_k["sales"], prev_k["sales"]))
    with c4:
        kpi_card("Конверсия", f"{cur_k['conversion']:.1f}%", mom_pct(cur_k["conversion"], prev_k["conversion"]))
    with c5:
        kpi_card("Средний чек", f"{cur_k['avg_check']:,.0f} ₽", mom_pct(cur_k["avg_check"], prev_k["avg_check"]))
    with c6:
        st.metric(
            "Возвраты/отмены",
            f"{metrics.get('returns_count', 0):,} шт.",
            f"{metrics.get('returns_pct', 0):.1f}%",
            delta_color="inverse",
        )

    g1, g2 = st.columns(2)

    with g1:
        weekly = df.groupby("week_start", as_index=False)["revenue"].sum().sort_values("week_start")
        if not weekly.empty:
            fig = px.line(weekly, x="week_start", y="revenue", title="Выручка по неделям", markers=True)
            if len(weekly) >= 2:
                x_num = np.arange(len(weekly))
                trend = np.polyval(np.polyfit(x_num, weekly["revenue"], 1), x_num)
                fig.add_trace(
                    go.Scatter(
                        x=weekly["week_start"],
                        y=trend,
                        mode="lines",
                        name="Тренд",
                        line=dict(dash="dash"),
                    )
                )
            fig.update_layout(yaxis_title="Выручка, ₽", xaxis_title="Неделя")
            st.plotly_chart(fig, use_container_width=True)

    with g2:
        top5 = df.groupby("category", as_index=False)["revenue"].sum().nlargest(5, "revenue")
        fig2 = px.bar(top5, x="category", y="revenue", title="Топ-5 категорий по выручке")
        st.plotly_chart(fig2, use_container_width=True)

    reg = df.groupby("region", as_index=False)["revenue"].sum().sort_values("revenue", ascending=True)
    if role == ROLE_DIRECTOR and not reg.empty:
        total = reg["revenue"].sum()
        reg["share_pct"] = reg["revenue"] / total * 100 if total else 0
        fig3 = px.bar(
            reg,
            x="share_pct",
            y="region",
            orientation="h",
            title="Доля регионов в выручке (%)",
            text="share_pct",
        )
        fig3.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        st.plotly_chart(fig3, use_container_width=True)

    if role == ROLE_SUPERVISOR and not df.empty:
        mgr = df.groupby("manager", as_index=False)["revenue"].sum().sort_values("revenue", ascending=True)
        fig4 = px.bar(mgr, x="revenue", y="manager", orientation="h", title="Выручка по менеджерам региона")
        st.plotly_chart(fig4, use_container_width=True)

    st.subheader("Управленческое резюме")
    for text in build_detailed_insights(df):
        st.markdown(text.replace("\n", "\n\n"))
    with st.expander("Краткая версия"):
        for text in build_insights_text(df):
            st.info(text)

    st.subheader("Детализация")
    detail = detail_table(df)
    st.dataframe(detail, use_container_width=True, hide_index=True)

    buf = BytesIO()
    detail.to_excel(buf, index=False, sheet_name="Detail")
    st.download_button(
        "Экспорт в Excel",
        data=buf.getvalue(),
        file_name="retailpro_detail.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
