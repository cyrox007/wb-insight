# WB Insight — обзор проекта

## Что это

WB Insight — web-сервис управленческой аналитики для продавцов Wildberries. Он заменяет исходную spreadsheet-модель серверным приложением: получает факты из официальных API Wildberries, хранит их по кабинетам продавца, добавляет данные, которых WB не знает (себестоимость, собственные расходы, налоговые параметры, план выручки), и строит единый аналитический слой для управления прибылью.

Ключевой принцип: frontend отображает рассчитанные backend-ом показатели и не является местом хранения бизнес-формул.

## Для кого

Первый стабильный релиз `1.0.0` ориентирован на владельца/руководителя магазина WB и аналитика, которым нужны:

- реальные деньги, а не только оборот;
- понимание прибыли и выплат;
- контроль рекламы, цен и остатков;
- unit-экономика по товарам;
- работа с несколькими WB-кабинетами в пределах тарифа;
- автоматическая синхронизация вместо ручной настройки таблиц.

## Scope WB Web v1

В `1.0.0` входят:

- регистрация и безопасная browser-session;
- роли и административная панель;
- тарифы, demo subscription и лимиты кабинетов;
- versioned legal consent;
- безопасное подключение Wildberries credentials;
- автоматическая account-scoped синхронизация;
- заказы, продажи и возвраты;
- товары, остатки и цены;
- реклама и воронка;
- платное хранение;
- финансовые отчёты, выплаты и reconciliation;
- историческая себестоимость;
- ручные расходы;
- месячный план выручки;
- Overview, Unit Economy, Finance, Inventory, Prices и Ads dashboards;
- реальный acquiring через Сбер после production onboarding;
- production deployment, monitoring, alerts и backup/restore baseline.

## Не входит в `1.0.0`

Не считаются доступными production-функциями до отдельного релиза:

- Ozon;
- AI-аналитик/чат;
- автоматический repricer/autobidder;
- SEO/генерация карточек;
- native Android/iOS;
- Wildberries OAuth 2.0 onboarding до готовности работы через Каталог решений.

Продуктовые гипотезы после `1.0.0` ведутся отдельно и не должны размывать стабильный релиз.

## Чем проект должен отличаться после stable

Стратегическое направление — не «ещё больше графиков» и не обычный AI-chat, а финансовая достоверность и управленческие решения:

- Financial Truth / data lineage: объяснимость каждой денежной цифры до исходного факта WB;
- Profit Bridge: разложение изменения прибыли по причинам в рублях;
- Marketplace Change Impact: персональный эффект изменений тарифов/условий WB;
- Capital Allocator: распределение ограниченного оборотного капитала между SKU/складами;
- Decision Memory: история решений и фактического эффекта конкретного продавца.

Эти направления относятся к post-1.0 backlog и не являются release blockers.

## Технологический стек

Backend: Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, Celery, Redis, httpx.

Frontend: Vue 3, Pinia, Vue Router, Axios, Vite; production runtime — nginx.

Deployment baseline: Docker images + Docker Compose, отдельные процессы migration/API/worker/beat/frontend, PostgreSQL и Redis.

## Состояние на 15 сентября 2026

- `main`: `0.9.0-alpha.5` после P28.
- активная ветка P29 готовит `0.9.0-alpha.6` с dependency/security hardening и полной ревизией документации.
- следующий stage — `0.9.0-beta.1`, только после feature freeze и production-like/data-accuracy acceptance.
- `1.0.0-rc.1` требует фактического закрытия WB/Sber/production/legal/ops blockers.
- `1.0.0` выпускается из проверенного RC.

Подробно: [`RELEASE_ROADMAP.md`](RELEASE_ROADMAP.md).
