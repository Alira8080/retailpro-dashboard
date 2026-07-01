# RetailPro — MVP дашборд продаж

## Скачать для заказчика

**[RetailPro_Delivery.zip (Release v1.1)](https://github.com/Alira8080/retailpro-dashboard/releases/download/v1.1/RetailPro_Delivery.zip)**

Репозиторий: https://github.com/Alira8080/retailpro-dashboard

### Состав v1.1
- Дашборд Power BI (3 роли) + данные
- **Пакет приёмки** `acceptance_package/` — очистка данных, сверка KPI, фильтры, управленческое резюме
- Инструкция `ИНСТРУКЦИЯ_ЗАКАЗЧИКУ.txt`

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
