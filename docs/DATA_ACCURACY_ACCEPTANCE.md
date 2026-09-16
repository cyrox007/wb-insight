# WB Insight — приёмочная сверка точности аналитики

Этот документ описывает обязательный data-accuracy gate перед переходом WB Web v1 в `0.9.0-beta.1`.

## Цель

CI подтверждает корректность кода на тестовых сценариях, но не доказывает, что итоговые деньги и KPI совпадают с реальными источниками продавца. Поэтому перед beta минимум один реальный WB-кабинет проверяется на фиксированных периодах.

Сверка должна отвечать на три вопроса:

1. какие исходные данные использованы;
2. какое значение получил WB Insight;
3. объясняется ли каждое расхождение принятой semantic-моделью и tolerance.

Необъяснённое денежное расхождение блокирует повышение release stage.

## Источники истины

Приоритет источников зависит от метрики:

1. официальный финансовый/операционный источник Wildberries для соответствующего домена;
2. данные продавца, введённые в WB Insight: историческая себестоимость, расходы, налоговые параметры;
3. исходная spreadsheet-модель проекта — как reference для пользовательской бизнес-логики и полноты показателей.

Spreadsheet не заменяет официальный WB source. Если её формула противоречит исправленной semantic-модели backend, расхождение документируется, а source of truth определяется по бизнес-смыслу и официальным данным.

## Минимальный набор метрик

Policy хранится в `ops/acceptance/wb_v1_metric_policy.json` и включает:

- заказанную сумму и количество;
- продажи и возвраты;
- выручку;
- комиссию WB;
- логистику;
- платное хранение;
- рекламные расходы;
- COGS;
- ручные расходы;
- налоги;
- прибыль;
- к выплате;
- остатки;
- текущую цену;
- выкуп;
- маржинальность;
- рентабельность;
- ДРР.

Policy versioned. Изменение tolerance считается изменением release-acceptance contract и должно проходить review.

### Полнота обязательных метрик

Для каждого acceptance-периода должны присутствовать **все метрики**, у которых в policy `required=true` или поле `required` не задано и поэтому действует значение по умолчанию `true`.

Runner сам добавляет отсутствующую policy-required метрику в результат со статусом `missing`. Поэтому входной JSON не может пройти acceptance только потому, что неудобную метрику забыли включить в `metrics`.

Input также не может ослабить policy и передать `"required": false` для policy-required метрики. Такой payload считается ошибкой acceptance contract и завершается кодом `2`.

В JSON/Markdown отчёте фиксируются:

- количество policy-required метрик на период;
- суммарное количество обязательных наблюдений;
- число `missing`;
- итоговый статус каждого наблюдения.

Beta data-accuracy evidence допустимо только при `missing=0` и отсутствии `fail`.

## Tolerance

Для денежных величин базовая политика — абсолютный tolerance `0.02 RUB`, если конкретная метрика не требует иного правила.

Для целочисленных количеств baseline — точное совпадение.

Для цены baseline — `0.01 RUB`.

Для процентных KPI baseline — `0.01` процентного пункта.

Runner поддерживает `absolute`, `relative`, `either` и `both` modes.

### Override tolerance

Входной acceptance-файл может изменить `tolerance_mode`, `absolute_tolerance` или `relative_tolerance_percent` относительно policy только при наличии непустого `override_reason`.

Пример допустимого исключения:

```json
{
  "metric": "revenue",
  "source": "WB financial report",
  "expected": "125000.42",
  "actual": "125000.90",
  "absolute_tolerance": "1.00",
  "override_reason": "Approved reconciliation difference for this historical period"
}
```

Отсутствующий `override_reason` при любом override считается ошибкой acceptance input и завершает runner кодом `2`.

`override_reason` не превращает расхождение автоматически в допустимое: новое значение всё равно должно попадать в указанный tolerance. Само решение об изменении tolerance должно быть reviewable и храниться вместе с release evidence.

Нельзя увеличивать tolerance только ради прохождения релиза без документированной причины и review.

## Формат входных данных

`ops/data_accuracy_acceptance.py` принимает JSON:

```json
{
  "dataset_id": "seller-acceptance-2026-09",
  "seller_alias": "seller-01",
  "periods": [
    {
      "label": "2026-08",
      "start_date": "2026-08-01",
      "end_date": "2026-08-31",
      "metrics": [
        {
          "metric": "revenue",
          "source": "WB financial report",
          "expected": "125000.42",
          "actual": "125000.42"
        }
      ]
    }
  ]
}
```

Пример выше демонстрирует форму одной метрики, а не минимально достаточный beta dataset: реальный acceptance-период обязан содержать все policy-required метрики.

Не помещайте в файл WB token, ФИО покупателя, номера телефонов, email, refresh/access JWT или merchant credentials. Для продавца используется нейтральный alias.

## Запуск

```bash
python3 ops/data_accuracy_acceptance.py \
  --input /secure/evidence/accuracy-input.json \
  --output-json /secure/evidence/data-accuracy.json \
  --output-md /secure/evidence/data-accuracy.md
```

Exit codes:

- `0` — все обязательные метрики присутствуют и находятся в tolerance;
- `1` — есть расхождение или отсутствует обязательная policy-метрика/значение;
- `2` — некорректный acceptance input/policy, попытка отключить required-метрику или tolerance override без `override_reason`.

Output содержит SHA-256 input и policy, поэтому результат можно связать с точным набором исходных значений без копирования секретных raw reports в Git.

## Выбор периодов

До beta рекомендуется минимум три фиксированных периода:

- один полный обычный месяц;
- период с возвратами и заметными WB удержаниями/логистикой;
- период, где есть реклама, COGS и ручные расходы.

Если функции paid storage или иные домены отсутствовали в выбранных периодах, нужен дополнительный период с реальными данными соответствующей capability.

Нулевое реальное значение допустимо и должно передаваться как `0`; отсутствие метрики и фактический ноль — разные состояния.

## Работа с расхождениями

При `fail` создаётся запись/issue с:

- metric id;
- seller alias;
- периодом;
- официальным источником;
- expected/actual;
- абсолютной и относительной разницей;
- формулой/semantic definition;
- причиной;
- решением: bugfix, source correction, documented semantic difference или изменение policy.

Если используется tolerance override, к записи также прикладывается `override_reason` и решение, которым исключение было одобрено.

После исправления acceptance запускается заново. Для beta итоговый canonical run должен быть green; ручное изменение JSON output запрещено.

## CI contract

Release integrity проверяет как минимум четыре класса сценариев:

1. полный fixture со всеми policy-required метриками проходит;
2. fixture с расхождением не проходит;
3. fixture с отсутствующими required-метриками получает `missing` и не проходит;
4. попытка отключить required-метрику или изменить tolerance без `override_reason` блокируется как некорректный input.

Это защищает beta-gate не только от арифметической ошибки, но и от неполной выборки или искусственного расширения tolerance.

## Spreadsheet reference

Исходный файл проекта содержал отдельные контуры рекламы, воронки, заказов, продаж/возвратов, комиссий WB, логистики/хранения, себестоимости, налогов/прочих расходов, прибыли, выплат, остатков, stockout, планов и цен. Эти области используются как coverage checklist.

При этом референсная таблица не является исполняемой production-спецификацией. Канонические формулы текущей версии находятся в backend semantic layer и `docs/DATA_AND_METRICS.md`.

## Evidence

Финальные `data-accuracy.json` и Markdown summary входят в beta release evidence. Они не коммитятся с реальными seller values в публичный/обычный source tree, а хранятся в защищённом release-evidence storage.

Связка evidence с commit/version выполняется через `ops/release_evidence.py`.
