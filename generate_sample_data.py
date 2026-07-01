"""Генерация ДЕМО-данных только для теста. Для продакшена используйте реальный CSV заказчика."""
from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd

REGIONS = ["Москва", "СПб", "Урал", "Сибирь", "Юг"]
CATEGORIES = ["Смартфоны", "Ноутбуки", "ТВ", "Наушники", "Планшеты", "Бытовая техника"]
MANAGERS = ["Иванов", "Петров", "Сидорова", "Козлов", "Морозова"]
STATUSES = ["completed", "completed", "completed", "return", "cancel"]

random.seed(42)


def generate(path: Path, rows: int = 800) -> None:
    today = date.today()
    start = today - timedelta(days=90)
    dates = [start + timedelta(days=random.randint(0, 90)) for _ in range(rows)]

    data = []
    for d in dates:
        status = random.choice(STATUSES)
        returns = 1 if status in {"return", "cancel"} else 0
        revenue = round(random.uniform(3000, 120000), 2)
        data.append(
            {
                "date": d.isoformat(),
                "region": random.choice(REGIONS),
                "category": random.choice(CATEGORIES),
                "manager": random.choice(MANAGERS),
                "revenue": 0 if status == "cancel" else revenue,
                "quantity": random.randint(1, 3),
                "discount_amount": round(revenue * random.uniform(0, 0.15), 2),
                "status": status,
                "returns": returns,
            }
        )

    pd.DataFrame(data).to_csv(path, index=False, encoding="utf-8-sig")
    print(f"Создано {rows} строк: {path}")


if __name__ == "__main__":
    generate(Path(__file__).parent / "sales.csv")
