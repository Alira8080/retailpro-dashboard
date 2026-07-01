# RetailPro — MVP дашборд продаж

## Скачать

**[RetailPro_Delivery.zip](https://github.com/Alira8080/retailpro-dashboard/releases/latest/download/RetailPro_Delivery.zip)** — полный пакет для заказчика.

## Быстрый старт

1. Установите [Power BI Desktop](https://powerbi.microsoft.com/desktop/)
2. Распакуйте архив
3. Откройте `RetailPro/RetailPro.pbip` или запустите `open_powerbi.bat`
4. Нажмите **Обновить** в Power BI

Подробно: `ИНСТРУКЦИЯ_ЗАКАЗЧИКУ.txt`

## Роли

| Вкладка | Кто видит |
|---------|-----------|
| Менеджер | Только свои продажи |
| Руководитель | Свой регион |
| Коммерческий директор | Вся компания |

## Обновление данных

```bash
pip install -r requirements.txt
python prepare_retailpro_data.py --input sales.csv
python build_powerbi_project.py
```

## Структура данных

Колонки CSV: `date`, `region`, `category`, `manager`, `revenue`, `quantity`, `discount_amount`, `status`, `returns`
