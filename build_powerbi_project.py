"""
Сборка проекта RetailPro.pbip для Power BI Desktop.

Запуск:
    python build_powerbi_project.py
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from prepare_retailpro_data import load_data, prepare_for_powerbi, export_powerbi_package

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "_pbip_template"
OUT = ROOT / "RetailPro"
DATA_DIR = ROOT / "powerbi_data"
SALES_CSV = ROOT / "sales.csv"

VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"
PAGE_W, PAGE_H = 1280, 1080

# Страницы отчёта по ролям
ROLE_PAGES = [
    {
        "key": "manager",
        "title": "Менеджер",
        "slicers": ("date", "category"),
        "region_chart": False,
        "manager_chart": False,
    },
    {
        "key": "supervisor",
        "title": "Руководитель",
        "slicers": ("date", "category", "manager"),
        "region_chart": False,
        "manager_chart": True,
    },
    {
        "key": "director",
        "title": "Коммерческий директор",
        "slicers": ("date", "region", "category", "manager"),
        "region_chart": True,
        "manager_chart": False,
    },
]


def uid() -> str:
    return uuid.uuid4().hex[:20]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: dict) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def csv_m_query(relative_csv: str, types: list[tuple[str, str]]) -> str:
    type_lines = ", ".join(f'{{"{n}", {t}}}' for n, t in types)
    return (
        "\t\t\tlet\n"
        f'\t\t\t\tSource = Csv.Document(File.Contents("{relative_csv}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]),\n'
        "\t\t\t\t#\"Promoted Headers\" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
        f'\t\t\t\t#"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{{type_lines}}})\n'
        "\t\t\tin\n"
        '\t\t\t\t#"Changed Type"'
    )


def measure_lines() -> str:
    measures = [
        ("Total Revenue", "SUM(retailpro_sales[revenue])", "#,0"),
        ("Applications Count", "COUNTROWS(retailpro_sales)", "#,0"),
        ("Sales Count", "SUM(retailpro_sales[is_sale])", "#,0"),
        ("Sales Revenue", "SUMX(retailpro_sales, IF(retailpro_sales[is_sale] = 1, retailpro_sales[revenue], 0))", "#,0"),
        ("Conversion %", "DIVIDE([Sales Count], [Applications Count])", "0.0%"),
        ("Average Check", "DIVIDE([Sales Revenue], [Sales Count])", "#,0"),
        ("Transactions Count", "[Applications Count]", "#,0"),
        ("Returns Count", "SUMX(retailpro_sales, IF(retailpro_sales[is_return_or_cancel] = 1, 1, 0))", "#,0"),
        ("Returns %", "DIVIDE([Returns Count], [Applications Count])", "0.0%"),
        ("Previous Month Revenue", "CALCULATE([Total Revenue], DATEADD(Calendar[Date], -1, MONTH))", "#,0"),
        ("Revenue MoM Growth %", "DIVIDE([Total Revenue] - [Previous Month Revenue], [Previous Month Revenue])", "+0.0%;-0.0%;0.0%"),
        ("Previous Month Applications", "CALCULATE([Applications Count], DATEADD(Calendar[Date], -1, MONTH))", None),
        ("Applications MoM Growth %", "DIVIDE([Applications Count] - [Previous Month Applications], [Previous Month Applications])", "+0.0%;-0.0%;0.0%"),
        ("Previous Month Sales", "CALCULATE([Sales Count], DATEADD(Calendar[Date], -1, MONTH))", None),
        ("Sales MoM Growth %", "DIVIDE([Sales Count] - [Previous Month Sales], [Previous Month Sales])", "+0.0%;-0.0%;0.0%"),
        ("Previous Month Average Check", "CALCULATE([Average Check], DATEADD(Calendar[Date], -1, MONTH))", None),
        ("Average Check MoM Growth %", "DIVIDE([Average Check] - [Previous Month Average Check], [Previous Month Average Check])", "+0.0%;-0.0%;0.0%"),
        ("Revenue MoM Label", 'VAR P = [Revenue MoM Growth %]\n\t\tRETURN IF(ISBLANK(P), "н/д", FORMAT(P, "+0.0%;-0.0%;0.0%") & " к пред. мес.")', None),
        ("Applications MoM Label", 'VAR P = [Applications MoM Growth %]\n\t\tRETURN IF(ISBLANK(P), "н/д", FORMAT(P, "+0.0%;-0.0%;0.0%") & " к пред. мес.")', None),
        ("Sales MoM Label", 'VAR P = [Sales MoM Growth %]\n\t\tRETURN IF(ISBLANK(P), "н/д", FORMAT(P, "+0.0%;-0.0%;0.0%") & " к пред. мес.")', None),
        ("Average Check MoM Label", 'VAR P = [Average Check MoM Growth %]\n\t\tRETURN IF(ISBLANK(P), "н/д", FORMAT(P, "+0.0%;-0.0%;0.0%") & " к пред. мес.")', None),
        (
            "Top 5 Categories Share %",
            "VAR Top5Rev = SUMX(TOPN(5, ADDCOLUMNS(VALUES(retailpro_sales[category]), \"@Rev\", CALCULATE([Total Revenue])), [@Rev], DESC), [@Rev])\n\t\tRETURN DIVIDE(Top5Rev, [Total Revenue])",
            "0.0%",
        ),
        (
            "Top 5 Category Revenue",
            "VAR Rank = RANKX(ALLSELECTED(retailpro_sales[category]), CALCULATE([Total Revenue]), , DESC, DENSE)\n\t\tRETURN IF(Rank <= 5, [Total Revenue])",
            "#,0",
        ),
        ("Regions Share %", "DIVIDE([Total Revenue], CALCULATE([Total Revenue], ALLSELECTED(retailpro_sales[region])))", "0.0%"),
        (
            "Insight Region Leader",
            'VAR T = TOPN(1, ADDCOLUMNS(VALUES(retailpro_sales[region]), "@R", CALCULATE([Total Revenue])), [@R], DESC)\n\t\tRETURN "Регион «" & MAXX(T, retailpro_sales[region]) & "» — основной канал (" & FORMAT(DIVIDE(MAXX(T, [@R]), [Total Revenue]), "0.0%") & " выручки)."',
            None,
        ),
        (
            "Insight Average Check MoM",
            'VAR P = [Average Check MoM Growth %]\n\t\tVAR D = IF(P >= 0, "вырос", "снизился")\n\t\tRETURN IF(ISBLANK(P), "Недостаточно данных для сравнения среднего чека.", "Средний чек " & D & " на " & FORMAT(ABS(P), "0.0%") & " к пред. месяцу.")',
            None,
        ),
        (
            "Insight Conversion",
            'VAR C = [Conversion %]\n\t\tVAR T = 0.6\n\t\tRETURN IF(C >= T, "Конверсия (" & FORMAT(C, "0.0%") & ") на уровне или выше ориентира (60%).", "Конверсия (" & FORMAT(C, "0.0%") & ") ниже ориентира 60% — нужен разбор отмен и возвратов.")',
            None,
        ),
        (
            "Management Summary",
            '[Insight Region Leader] & UNICHAR(10) & UNICHAR(10) & [Insight Average Check MoM] & UNICHAR(10) & UNICHAR(10) & [Insight Conversion]',
            None,
        ),
        ("Insight Section Title", '"Управленческое резюме"', None),
    ]
    lines: list[str] = []
    for name, expr, fmt in measures:
        if "\n" in expr:
            lines.append(f"\tmeasure '{name}' =\n\t\t{expr}")
        else:
            lines.append(f"\tmeasure '{name}' = {expr}")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
    return "\n\n".join(lines) + "\n"


def build_semantic_model() -> None:
    sm = OUT / "RetailPro.SemanticModel"
    rel_csv = "..\\..\\powerbi_data\\retailpro_sales.csv"
    cal_csv = "..\\..\\powerbi_data\\Calendar.csv"
    access_csv = "..\\..\\powerbi_data\\UserAccess.csv"

    sales_types = [
        ("date", "type date"),
        ("region", "type text"),
        ("category", "type text"),
        ("manager", "type text"),
        ("revenue", "type number"),
        ("quantity", "Int64.Type"),
        ("discount_amount", "type number"),
        ("status", "type text"),
        ("returns", "Int64.Type"),
        ("week_start", "type date"),
        ("is_return_or_cancel", "Int64.Type"),
        ("is_application", "Int64.Type"),
        ("is_sale", "Int64.Type"),
    ]
    cal_types = [
        ("Date", "type date"),
        ("Year", "Int64.Type"),
        ("Month", "Int64.Type"),
        ("YearMonth", "type text"),
    ]

    write_text(
        sm / "definition" / "database.tmdl",
        "database\n\tcompatibilityLevel: 1567\n",
    )
    access_types = [
        ("user_login", "type text"),
        ("role", "type text"),
        ("manager", "type text"),
        ("region", "type text"),
    ]
    write_text(
        sm / "definition" / "tables" / "UserAccess.tmdl",
        f"""table UserAccess
\tlineageTag: {uid()}

\tcolumn user_login
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsourceColumn: user_login

\tcolumn role
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsourceColumn: role

\tcolumn manager
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsourceColumn: manager

\tcolumn region
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsourceColumn: region

\tpartition UserAccess = m
\t\tmode: import
\t\tsource =
{csv_m_query(access_csv, access_types)}
""",
    )
    write_text(
        sm / "definition" / "roles" / "Менеджер.tmdl",
        """role 'Менеджер'
\tmodelPermission: read

\ttablePermission retailpro_sales =
\t\tVAR AllowedManager =
\t\t\tCALCULATE(
\t\t\t\tMAX(UserAccess[manager]),
\t\t\t\tUserAccess[user_login] = USERNAME(),
\t\t\t\tUserAccess[role] = "Менеджер"
\t\t\t)
\t\tRETURN retailpro_sales[manager] = AllowedManager
""",
    )
    write_text(
        sm / "definition" / "roles" / "Руководитель.tmdl",
        """role 'Руководитель'
\tmodelPermission: read

\ttablePermission retailpro_sales =
\t\tVAR AllowedRegion =
\t\t\tCALCULATE(
\t\t\t\tMAX(UserAccess[region]),
\t\t\t\tUserAccess[user_login] = USERNAME(),
\t\t\t\tUserAccess[role] = "Руководитель"
\t\t\t)
\t\tRETURN retailpro_sales[region] = AllowedRegion
""",
    )
    write_text(
        sm / "definition" / "roles" / "Коммерческий директор.tmdl",
        """role 'Коммерческий директор'
\tmodelPermission: read
""",
    )
    write_text(
        sm / "definition" / "model.tmdl",
        """model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

\tannotation __PBI_TimeIntelligenceEnabled = 1
\tannotation PBI_ProTooling = ["DevMode"]

\tref cultureInfo en-US
\tref table retailpro_sales
\tref table Calendar
\tref table UserAccess
\tref table _Measures
\tref role 'Менеджер'
\tref role 'Руководитель'
\tref role 'Коммерческий директор'
""",
    )
    write_text(sm / "definition" / "cultures" / "en-US.tmdl", "cultureInfo en-US\n")
    write_text(
        sm / "definition" / "relationships.tmdl",
        f"relationship {uid()}\n\tfromColumn: retailpro_sales.date\n\ttoColumn: Calendar.Date\n",
    )
    write_text(
        sm / "definition" / "tables" / "retailpro_sales.tmdl",
        f"""table retailpro_sales
\tlineageTag: {uid()}

\tcolumn date
\t\tdataType: dateTime
\t\tformatString: Short Date
\t\tlineageTag: {uid()}
\t\tsummarizeBy: none
\t\tsourceColumn: date

\tcolumn region
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsummarizeBy: none
\t\tsourceColumn: region

\tcolumn category
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsummarizeBy: none
\t\tsourceColumn: category

\tcolumn manager
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsummarizeBy: none
\t\tsourceColumn: manager

\tcolumn revenue
\t\tdataType: double
\t\tformatString: #,0
\t\tlineageTag: {uid()}
\t\tsourceColumn: revenue

\tcolumn quantity
\t\tdataType: int64
\t\tlineageTag: {uid()}
\t\tsourceColumn: quantity

\tcolumn discount_amount
\t\tdataType: double
\t\tlineageTag: {uid()}
\t\tsourceColumn: discount_amount

\tcolumn status
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsourceColumn: status

\tcolumn returns
\t\tdataType: int64
\t\tlineageTag: {uid()}
\t\tsourceColumn: returns

\tcolumn week_start
\t\tdataType: dateTime
\t\tformatString: Short Date
\t\tlineageTag: {uid()}
\t\tsummarizeBy: none
\t\tsourceColumn: week_start

\tcolumn is_return_or_cancel
\t\tdataType: int64
\t\tlineageTag: {uid()}
\t\tsourceColumn: is_return_or_cancel

\tcolumn is_application
\t\tdataType: int64
\t\tlineageTag: {uid()}
\t\tsourceColumn: is_application

\tcolumn is_sale
\t\tdataType: int64
\t\tlineageTag: {uid()}
\t\tsourceColumn: is_sale

\tpartition retailpro_sales = m
\t\tmode: import
\t\tsource =
{csv_m_query(rel_csv, sales_types)}
""",
    )
    write_text(
        sm / "definition" / "tables" / "Calendar.tmdl",
        f"""table Calendar
\tdataCategory: Time
\tlineageTag: {uid()}

\tcolumn Date
\t\tdataType: dateTime
\t\tformatString: Short Date
\t\tisKey
\t\tlineageTag: {uid()}
\t\tsummarizeBy: none
\t\tsourceColumn: Date

\tcolumn Year
\t\tdataType: int64
\t\tlineageTag: {uid()}
\t\tsourceColumn: Year

\tcolumn Month
\t\tdataType: int64
\t\tlineageTag: {uid()}
\t\tsourceColumn: Month

\tcolumn YearMonth
\t\tdataType: string
\t\tlineageTag: {uid()}
\t\tsourceColumn: YearMonth

\tpartition Calendar = m
\t\tmode: import
\t\tsource =
{csv_m_query(cal_csv, cal_types)}
""",
    )
    write_text(
        sm / "definition" / "tables" / "_Measures.tmdl",
        f"table _Measures\n\tlineageTag: {uid()}\n\n{measure_lines()}",
    )
    write_json(
        sm / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {},
        },
    )
    write_json(
        sm / "diagramLayout.json",
        {
            "version": "1.1.0",
            "diagrams": [
                {
                    "ordinal": 0,
                    "scrollPosition": {"x": 0, "y": 0},
                    "nodes": [
                        {"location": {"x": 0, "y": 0}, "nodeIndex": "retailpro_sales", "size": {"height": 300, "width": 234}},
                        {"location": {"x": 300, "y": 0}, "nodeIndex": "Calendar", "size": {"height": 200, "width": 234}},
                        {"location": {"x": 150, "y": 350}, "nodeIndex": "_Measures", "size": {"height": 104, "width": 234}},
                    ],
                    "name": "All tables",
                }
            ],
            "selectedDiagram": "All tables",
            "defaultDiagram": "All tables",
        },
    )
    shutil.copy2(TEMPLATE / "Template.SemanticModel" / ".platform", sm / ".platform")
    plat = json.loads((sm / ".platform").read_text(encoding="utf-8"))
    plat["metadata"]["displayName"] = "RetailPro"
    write_json(sm / ".platform", plat)


def vco() -> dict:
    off = {"expr": {"Literal": {"Value": "false"}}}
    return {
        "background": [{"properties": {"show": off}}],
        "border": [{"properties": {"show": off}}],
        "dropShadow": [{"properties": {"show": off}}],
        "title": [{"properties": {"show": off}}],
    }


def col_field(table: str, column: str) -> dict:
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column,
            }
        },
        "queryRef": f"{table}.{column}",
        "active": True,
    }


def meas_field(measure: str) -> dict:
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": "_Measures"}},
                "Property": measure,
            }
        },
        "queryRef": f"_Measures.{measure}",
    }


def make_visual(name: str, vtype: str, x: float, y: float, w: float, h: float, visual: dict) -> dict:
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": int(y)},
        "visual": {"visualType": vtype, **visual},
    }


def card_visual(measure: str, subtitle: str | None = None) -> dict:
    v: dict = {
        "query": {"queryState": {"Values": {"projections": [meas_field(measure)]}}},
        "visualContainerObjects": vco(),
    }
    if subtitle:
        v["query"]["queryState"]["Values"]["projections"].append(meas_field(subtitle))
    return v


def slicer_visual(table: str, column: str) -> dict:
    return {
        "query": {"queryState": {"Values": {"projections": [col_field(table, column)]}}},
        "objects": {
            "general": [{"properties": {"orientation": {"expr": {"Literal": {"Value": "'Vertical'"}}}}}],
            "selection": [{"properties": {"selectAllCheckboxEnabled": {"expr": {"Literal": {"Value": "true"}}}}}],
        },
        "visualContainerObjects": vco(),
    }


def build_role_page(cfg: dict) -> str:
    """Одна страница отчёта под роль."""
    page_id = uid()
    visuals_dir = OUT / "RetailPro.Report" / "definition" / "pages" / page_id / "visuals"
    visuals: list[dict] = []

    sx = 10
    if "date" in cfg["slicers"]:
        visuals.append(make_visual(uid(), "slicer", sx, 10, 280, 90, slicer_visual("Calendar", "Date")))
        sx += 290
    if "region" in cfg["slicers"]:
        visuals.append(make_visual(uid(), "slicer", sx, 10, 200, 90, slicer_visual("retailpro_sales", "region")))
        sx += 210
    if "category" in cfg["slicers"]:
        visuals.append(make_visual(uid(), "slicer", sx, 10, 200, 90, slicer_visual("retailpro_sales", "category")))
        sx += 210
    if "manager" in cfg["slicers"]:
        visuals.append(make_visual(uid(), "slicer", sx, 10, 200, 90, slicer_visual("retailpro_sales", "manager")))

    kpis = [
        ("Total Revenue", "Revenue MoM Label", 10, 195),
        ("Applications Count", "Applications MoM Label", 210, 195),
        ("Sales Count", "Sales MoM Label", 410, 195),
        ("Conversion %", None, 610, 195),
        ("Average Check", "Average Check MoM Label", 810, 195),
        ("Returns Count", None, 1010, 195),
    ]
    for measure, sub, x, w in kpis:
        visuals.append(make_visual(uid(), "card", x, 110, w, 95, card_visual(measure, sub)))
    visuals.append(make_visual(uid(), "card", 1010, 210, 120, 45, card_visual("Returns %")))

    visuals.append(
        make_visual(
            uid(), "lineChart", 10, 220, 620, 240,
            {
                "query": {
                    "queryState": {
                        "Category": {"projections": [col_field("retailpro_sales", "week_start")]},
                        "Y": {"projections": [meas_field("Total Revenue")]},
                    }
                },
                "objects": {"lineStyles": [{"properties": {"strokeWidth": {"expr": {"Literal": {"Value": "2D"}}}, "showMarker": {"expr": {"Literal": {"Value": "true"}}}}}]},
                "visualContainerObjects": vco(),
            },
        )
    )
    visuals.append(
        make_visual(
            uid(), "clusteredBarChart", 640, 220, 620, 240,
            {
                "query": {
                    "queryState": {
                        "Category": {"projections": [col_field("retailpro_sales", "category")]},
                        "Y": {"projections": [meas_field("Top 5 Category Revenue")]},
                    },
                    "sortDefinition": {"sort": [{"field": meas_field("Top 5 Category Revenue")["field"], "direction": "Descending"}]},
                },
                "visualContainerObjects": vco(),
            },
        )
    )

    if cfg["region_chart"]:
        visuals.append(
            make_visual(
                uid(), "clusteredBarChart", 10, 470, 1250, 200,
                {
                    "query": {
                        "queryState": {
                            "Category": {"projections": [col_field("retailpro_sales", "region")]},
                            "Y": {"projections": [meas_field("Regions Share %")]},
                        },
                        "sortDefinition": {"sort": [{"field": meas_field("Regions Share %")["field"], "direction": "Descending"}]},
                    },
                    "visualContainerObjects": vco(),
                },
            )
        )
    elif cfg["manager_chart"]:
        visuals.append(
            make_visual(
                uid(), "clusteredBarChart", 10, 470, 1250, 200,
                {
                    "query": {
                        "queryState": {
                            "Category": {"projections": [col_field("retailpro_sales", "manager")]},
                            "Y": {"projections": [meas_field("Total Revenue")]},
                        },
                        "sortDefinition": {"sort": [{"field": meas_field("Total Revenue")["field"], "direction": "Descending"}]},
                    },
                    "visualContainerObjects": vco(),
                },
            )
        )

    visuals.append(
        make_visual(
            uid(), "card", 10, 665, 200, 35,
            card_visual("Insight Section Title"),
        )
    )
    visuals.append(make_visual(uid(), "card", 10, 700, 1250, 120, card_visual("Management Summary")))

    visuals.append(
        make_visual(
            uid(), "tableEx", 10, 830, 1250, 230,
            {
                "query": {
                    "queryState": {
                        "Values": {
                            "projections": [
                                col_field("retailpro_sales", "date"),
                                col_field("retailpro_sales", "region"),
                                col_field("retailpro_sales", "category"),
                                col_field("retailpro_sales", "revenue"),
                                col_field("retailpro_sales", "manager"),
                            ]
                        }
                    }
                },
                "visualContainerObjects": vco(),
            },
        )
    )

    for vdata in visuals:
        write_json(visuals_dir / vdata["name"] / "visual.json", vdata)

    write_json(
        OUT / "RetailPro.Report" / "definition" / "pages" / page_id / "page.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": page_id,
            "displayName": cfg["title"],
            "displayOption": "FitToPage",
            "height": PAGE_H,
            "width": PAGE_W,
            "objects": {"outspace": [{"properties": {"color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#F5F7FA'"}}}}}}}]},
        },
    )
    return page_id


def build_report() -> list[str]:
    page_ids = [build_role_page(cfg) for cfg in ROLE_PAGES]

    write_json(
        OUT / "RetailPro.Report" / "definition" / "pages" / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": page_ids,
            "activePageName": page_ids[-1],
        },
    )

    report = json.loads((TEMPLATE / "Template.Report" / "definition" / "report.json").read_text(encoding="utf-8"))
    report["settings"]["exportDataMode"] = "AllowSummarizedAndUnderlying"
    write_json(OUT / "RetailPro.Report" / "definition" / "report.json", report)
    shutil.copy2(TEMPLATE / "Template.Report" / "definition" / "version.json", OUT / "RetailPro.Report" / "definition" / "version.json")

    static = OUT / "RetailPro.Report" / "StaticResources" / "SharedResources" / "BaseThemes"
    static.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        TEMPLATE / "Template.Report" / "StaticResources" / "SharedResources" / "BaseThemes" / "CY26SU02.json",
        static / "CY26SU02.json",
    )

    write_json(
        OUT / "RetailPro.Report" / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../RetailPro.SemanticModel"}},
        },
    )
    shutil.copy2(TEMPLATE / "Template.Report" / ".platform", OUT / "RetailPro.Report" / ".platform")
    plat = json.loads((OUT / "RetailPro.Report" / ".platform").read_text(encoding="utf-8"))
    plat["metadata"]["displayName"] = "RetailPro"
    write_json(OUT / "RetailPro.Report" / ".platform", plat)

    write_json(
        OUT / "RetailPro.pbip",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "RetailPro.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    return page_ids


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit("Нет _pbip_template. Запустите: git clone ... или пересоберите проект.")

    if not SALES_CSV.exists():
        import generate_sample_data

        generate_sample_data.generate(SALES_CSV)

    df = prepare_for_powerbi(load_data(SALES_CSV))
    export_powerbi_package(df, DATA_DIR)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    build_semantic_model()
    build_report()

    print("Готово!")
    print(f"Откройте в Power BI Desktop: {OUT / 'RetailPro.pbip'}")
    print(f"Данные: {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
