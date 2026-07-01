# RetailPro — MVP дашборд продаж

## Скачать для заказчика

**[RetailPro_Delivery.zip (Release v1.2)](https://github.com/Alira8080/retailpro-dashboard/releases/download/v1.2/RetailPro_Delivery.zip)**

Репозиторий: https://github.com/Alira8080/retailpro-dashboard

### Состав v1.2
- **ОПИСАНИЕ_РЕЗУЛЬТАТА.txt** в корне архива — подтверждение KPI, фильтров, управленческое резюме
- **НАЧНИТЕ_ЗДЕСЬ.txt** — точка входа для приёмки
- Пакет приёмки `acceptance_package/` с автотестом фильтров

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
