<script setup>
const openRegister = () => window.dispatchEvent(new CustomEvent('wb:open-register'))
const openLogin = () => window.dispatchEvent(new CustomEvent('wb:open-login'))

const problems = [
  { icon: '₽', title: 'Теряется прибыль', text: 'Выручка растёт, а денег больше не становится — комиссии и расходы съедают результат.' },
  { icon: '↗', title: 'Непонятная экономика', text: 'Сложно быстро понять, какие товары действительно зарабатывают, а какие создают оборот без прибыли.' },
  { icon: '◎', title: 'Реклама работает вслепую', text: 'Бюджет расходуется, но не всегда понятно, какие кампании и товары возвращают вложения.' },
  { icon: '□', title: 'Заканчиваются остатки', text: 'Нет единого взгляда на скорость продаж, остатки и риск упустить выручку из-за out-of-stock.' },
  { icon: '%', title: 'Комиссии и удержания', text: 'Финансовые отчёты WB приходится собирать вручную, чтобы объяснить разницу между продажами и выплатой.' },
  { icon: '≡', title: 'Слишком много таблиц', text: 'Данные разбросаны между кабинетами, Excel и отчётами. На сбор уходит время, которое можно тратить на рост.' },
]

const features = [
  { icon: '◫', title: 'Аналитика в одном месте', text: 'Продажи, возвраты, товары, остатки, реклама и финансы в едином рабочем контуре.' },
  { icon: '₽', title: 'Прибыль и маржинальность', text: 'Смотрите экономику по товарам с учётом себестоимости, комиссий, логистики и расходов.' },
  { icon: '◔', title: 'Финансовый контроль', text: 'Сводите начисления, удержания и выплаты WB в понятную картину движения денег.' },
  { icon: '⌁', title: 'Остатки и stockout', text: 'Находите товары с риском дефицита и планируйте пополнение до того, как продажи остановятся.' },
  { icon: '↗', title: 'Реклама и воронка', text: 'Сопоставляйте рекламные расходы с продажами и оценивайте эффективность кампаний.' },
  { icon: '⚡', title: 'Автоматическая синхронизация', text: 'Система сама собирает доступные данные WB и обновляет рабочие показатели.' },
  { icon: '🔔', title: 'Контроль важных событий', text: 'Следите за критичными изменениями и отклонениями, не открывая десятки отчётов.' },
  { icon: '◎', title: 'Несколько кабинетов', text: 'Работайте с несколькими WB-аккаунтами и переключайтесь между ними без смешивания данных.' },
]

const roadmap = [
  { title: 'AI-рекомендации', text: 'Подсказки по точкам роста, проблемам и приоритетным действиям на основе ваших показателей.' },
  { title: 'Прогноз спроса', text: 'Более глубокое планирование поставок и прогнозирование потребности в остатках.' },
  { title: 'Анализ конкурентов', text: 'Сравнение рыночной динамики, цен и видимых изменений в конкурентном окружении.' },
  { title: 'Рекомендации по ценам', text: 'Сценарии изменения цены с фокусом на маржу, спрос и целевую прибыль.' },
  { title: 'Умные уведомления', text: 'Больше сценариев оповещений и удобная доставка важных событий в привычные каналы.' },
  { title: 'Другие маркетплейсы', text: 'Расширение единой модели аналитики за пределы Wildberries.' },
]

const faqs = [
  ['Нужно ли загружать Excel вручную?', 'Нет. Основной сценарий — подключить кабинет Wildberries и синхронизировать данные через API.'],
  ['Можно ли подключить несколько кабинетов?', 'Да. Архитектура системы поддерживает раздельную работу с несколькими marketplace-аккаунтами.'],
  ['Мои токены Wildberries будут видны в интерфейсе?', 'Нет. Чувствительные credentials обрабатываются на сервере и не должны отображаться обратно в открытом виде.'],
  ['Что будет после регистрации?', 'Вы создаёте аккаунт, подключаете Wildberries и переходите к синхронизации данных и рабочим дашбордам.'],
]
</script>

<template>
  <div class="landing">
    <section class="hero">
      <div class="landing-shell hero__grid">
        <div class="hero__copy">
          <div class="eyebrow"><span class="eyebrow__dot"></span> Аналитика продавца Wildberries без хаоса в таблицах</div>
          <h1>Управляйте <span>прибылью</span> на Wildberries, а не просто смотрите на выручку</h1>
          <p class="hero__lead">
            WB Insight собирает ключевые показатели продавца в одном месте, помогает увидеть реальную экономику,
            находить точки роста и принимать решения на основе данных.
          </p>
          <div class="hero__actions">
            <button type="button" class="cta cta--primary" @click="openRegister">
              Попробовать бесплатно <span>→</span>
            </button>
            <a class="cta cta--secondary" href="#product">Посмотреть возможности</a>
          </div>
          <div class="hero__meta">
            <span>✓ Быстрый старт</span>
            <span>✓ Без ручной загрузки отчётов</span>
            <span>✓ Подключение через API WB</span>
          </div>
        </div>

        <div class="product-preview" id="product" aria-label="Демонстрационный интерфейс WB Insight">
          <div class="product-preview__top">
            <div class="preview-brand"><span class="preview-brand__mark">WB</span> Insight</div>
            <span class="demo-badge">Демо-данные</span>
          </div>
          <div class="preview-layout">
            <aside class="preview-nav">
              <span class="active">Обзор</span>
              <span>Юнит-экономика</span>
              <span>Финансы</span>
              <span>Остатки</span>
              <span>Цены</span>
              <span>Реклама</span>
            </aside>
            <div class="preview-main">
              <div class="preview-title">
                <div>
                  <small>Главная</small>
                  <strong>Обзор бизнеса</strong>
                </div>
                <span>Последние 30 дней</span>
              </div>
              <div class="metrics">
                <article><small>Выручка</small><strong>1 428 320 ₽</strong><em>+12,4%</em></article>
                <article><small>Прибыль</small><strong>312 465 ₽</strong><em>+8,7%</em></article>
                <article><small>Маржа</small><strong>21,9%</strong><em>+2,1 п.п.</em></article>
                <article><small>Заказы</small><strong>1 842</strong><em>+6,4%</em></article>
              </div>
              <div class="chart-card">
                <div class="chart-card__head"><strong>Динамика продаж</strong><span>Выручка</span></div>
                <svg viewBox="0 0 700 210" role="img" aria-label="Демонстрационный график продаж">
                  <defs>
                    <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stop-color="#6d5dfc" stop-opacity=".25"/>
                      <stop offset="100%" stop-color="#6d5dfc" stop-opacity="0"/>
                    </linearGradient>
                  </defs>
                  <path d="M10 168 C70 150,90 154,130 131 S210 149,260 112 S330 116,380 89 S455 110,510 69 S600 91,690 38 L690 200 L10 200 Z" fill="url(#area)"/>
                  <path d="M10 168 C70 150,90 154,130 131 S210 149,260 112 S330 116,380 89 S455 110,510 69 S600 91,690 38" fill="none" stroke="#6d5dfc" stroke-width="5" stroke-linecap="round"/>
                </svg>
              </div>
              <div class="preview-bottom">
                <div class="profit-card">
                  <small>Структура расходов</small>
                  <div class="donut"></div>
                  <strong>Держите маржу под контролем</strong>
                </div>
                <div class="top-card">
                  <small>Товары по прибыли</small>
                  <p><span>Футболка oversize</span><b>125 430 ₽</b></p>
                  <p><span>Кроссовки</span><b>98 221 ₽</b></p>
                  <p><span>Худи</span><b>60 415 ₽</b></p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="section section--soft" id="problems">
      <div class="landing-shell">
        <div class="section-heading">
          <p class="section-kicker">Знакомая ситуация?</p>
          <h2>Почему прибыль продавца теряется между отчётами</h2>
          <p>Проблема обычно не в отсутствии данных. Проблема в том, что они разбросаны, запаздывают и не отвечают на вопрос: «Что делать дальше?»</p>
        </div>
        <div class="problem-grid">
          <article v-for="item in problems" :key="item.title" class="problem-card">
            <span class="problem-card__icon">{{ item.icon }}</span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section" id="features">
      <div class="landing-shell">
        <div class="section-heading section-heading--split">
          <div>
            <p class="section-kicker">Наше решение</p>
            <h2>Вся аналитика продавца в одной системе</h2>
          </div>
          <p>Не ещё один отчёт, а рабочее пространство, где продажи, экономика, остатки, реклама и деньги связаны между собой.</p>
        </div>
        <div class="feature-grid">
          <article v-for="item in features" :key="item.title" class="feature-card">
            <span>{{ item.icon }}</span>
            <div><h3>{{ item.title }}</h3><p>{{ item.text }}</p></div>
          </article>
        </div>
      </div>
    </section>

    <section class="section proof">
      <div class="landing-shell">
        <div class="proof__panel">
          <div>
            <p class="section-kicker">Главное — действие</p>
            <h2>Из цифр — в понятные решения</h2>
          </div>
          <div class="proof__items">
            <article><strong>01</strong><span>Поймите, где зарабатываете</span></article>
            <article><strong>02</strong><span>Найдите потери и отклонения</span></article>
            <article><strong>03</strong><span>Сфокусируйтесь на точках роста</span></article>
            <article><strong>04</strong><span>Проверяйте результат изменений</span></article>
          </div>
        </div>
      </div>
    </section>

    <section class="section steps" id="how">
      <div class="landing-shell">
        <div class="section-heading">
          <p class="section-kicker">Как это работает</p>
          <h2>Начните за три шага</h2>
        </div>
        <div class="steps__grid">
          <article><b>1</b><h3>Создайте аккаунт</h3><p>Пройдите регистрацию и войдите в личный кабинет WB Insight.</p></article>
          <article><b>2</b><h3>Подключите Wildberries</h3><p>Добавьте marketplace credential через защищённый серверный контур.</p></article>
          <article><b>3</b><h3>Получайте аналитику</h3><p>Синхронизируйте данные и работайте с дашбордами, финансами, остатками и рекламой.</p></article>
        </div>
        <div class="center-cta"><button class="cta cta--primary" type="button" @click="openRegister">Создать аккаунт →</button></div>
      </div>
    </section>

    <section class="section roadmap" id="roadmap">
      <div class="landing-shell">
        <div class="section-heading section-heading--split">
          <div>
            <p class="section-kicker">Дальше — больше</p>
            <h2>Что мы планируем развивать</h2>
          </div>
          <p>Эти возможности входят в направление развития продукта. Они показаны как roadmap и могут меняться по мере развития сервиса.</p>
        </div>
        <div class="roadmap-grid">
          <article v-for="item in roadmap" :key="item.title">
            <span>В планах</span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section faq" id="faq">
      <div class="landing-shell faq__grid">
        <div class="faq__intro">
          <p class="section-kicker">FAQ</p>
          <h2>Перед стартом</h2>
          <p>Короткие ответы на основные вопросы перед регистрацией.</p>
          <button type="button" class="text-link" @click="openLogin">Уже есть аккаунт? Войти →</button>
        </div>
        <div class="faq__items">
          <details v-for="item in faqs" :key="item[0]">
            <summary>{{ item[0] }} <span>+</span></summary>
            <p>{{ item[1] }}</p>
          </details>
        </div>
      </div>
    </section>

    <section class="final-cta">
      <div class="landing-shell final-cta__panel">
        <div>
          <p class="section-kicker">Готовы увидеть бизнес целиком?</p>
          <h2>Превратите данные Wildberries в управляемую систему</h2>
          <p>Начните с регистрации, подключите кабинет и переходите от ручного сбора цифр к регулярной аналитике.</p>
        </div>
        <button type="button" class="cta cta--white" @click="openRegister">Попробовать WB Insight →</button>
      </div>
    </section>

    <footer class="landing-footer">
      <div class="landing-shell landing-footer__inner">
        <div class="landing-footer__brand"><span>WB</span><strong>Insight</strong></div>
        <nav>
          <a href="#features">Возможности</a>
          <a href="#how">Как работает</a>
          <a href="#roadmap">Roadmap</a>
          <a href="#faq">FAQ</a>
          <RouterLink to="/terms">Условия</RouterLink>
          <RouterLink to="/privacy">Конфиденциальность</RouterLink>
        </nav>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  --ink: var(--text-color);
  --muted: var(--text-muted);
  --line: var(--border-color);
  --violet: var(--secondary-color);
  --violet-2: var(--secondary-hover);
  --pink: var(--accent-color);
  --surface: var(--card-bg);
  --soft: var(--light-bg);
  color: var(--ink);
  background:
    radial-gradient(circle at 74% 4%, rgba(99,91,255,.13), transparent 28rem),
    radial-gradient(circle at 12% 10%, rgba(236,72,153,.07), transparent 22rem),
    var(--dark-bg);
  overflow: hidden;
}
.landing-shell { width: min(100% - 40px, 1240px); margin: 0 auto; }
.hero { padding: 74px 0 88px; }
.hero__grid { display: grid; grid-template-columns: .9fr 1.15fr; gap: 52px; align-items: center; }
.eyebrow,.section-kicker { color: var(--secondary-color); font-weight: 800; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; }
.eyebrow { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 999px; background: color-mix(in srgb, var(--surface) 88%, transparent); }
.eyebrow__dot { width: 7px; height: 7px; border-radius: 50%; background: linear-gradient(135deg,var(--violet),var(--pink)); box-shadow: 0 0 0 5px rgba(99,91,255,.08); }
.hero h1 { margin-top: 22px; font-size: clamp(42px,5.3vw,72px); line-height: 1.02; letter-spacing: -.055em; color: var(--ink); }
.hero h1 span { color: var(--violet); }
.hero__lead { max-width: 650px; margin-top: 24px; color: var(--muted); font-size: 18px; line-height: 1.72; }
.hero__actions { display: flex; gap: 12px; margin-top: 30px; flex-wrap: wrap; }
.cta { min-height: 50px; padding: 0 20px; display: inline-flex; align-items: center; justify-content: center; gap: 10px; border-radius: 13px; border: 1px solid transparent; font-weight: 800; cursor: pointer; transition: transform .18s ease, box-shadow .18s ease, background .18s ease; }
.cta:hover { transform: translateY(-2px); }
.cta--primary { color: #fff; background: linear-gradient(135deg,#625bff,#7139e7); box-shadow: 0 14px 30px rgba(99,91,255,.25); }
.cta--secondary { color: var(--ink); border-color: var(--line); background: color-mix(in srgb, var(--surface) 88%, transparent); }
.cta--white { color: #4b42e8; background: #fff; box-shadow: 0 15px 30px rgba(20,20,70,.18); }
.hero__meta { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 20px; color: var(--muted); font-size: 12px; font-weight: 650; }

.product-preview { border: 1px solid rgba(112,99,255,.18); border-radius: 24px; background: color-mix(in srgb, var(--surface) 94%, transparent); box-shadow: 0 34px 80px rgba(61,48,145,.18); overflow: hidden; transform: perspective(1300px) rotateY(-2deg) rotateX(1deg); }
.product-preview__top { min-height: 54px; padding: 0 18px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid var(--line); }
.preview-brand { display:flex; align-items:center; gap:8px; font-weight:900; }
.preview-brand__mark { padding:5px 7px; color:#fff; font-size:10px; border-radius:7px; background:linear-gradient(135deg,#625bff,#8b5cf6); }
.demo-badge { padding:6px 9px; border-radius:999px; background:color-mix(in srgb, var(--secondary-color) 11%, var(--surface)); color:var(--secondary-color); font-size:10px; font-weight:800; }
.preview-layout { display:grid; grid-template-columns:128px 1fr; min-height:460px; }
.preview-nav { padding:18px 10px; display:flex; flex-direction:column; gap:6px; background:var(--soft); border-right:1px solid var(--line); }
.preview-nav span { padding:8px 9px; border-radius:8px; color:var(--muted); font-size:10px; font-weight:700; }
.preview-nav .active { color:var(--secondary-color); background:color-mix(in srgb, var(--secondary-color) 12%, var(--surface)); }
.preview-main { min-width:0; padding:18px; }
.preview-title { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.preview-title div { display:flex; flex-direction:column; gap:2px; }
.preview-title small { color:var(--text-subtle); font-size:9px; }
.preview-title strong { font-size:14px; }
.preview-title > span { color:var(--text-subtle); font-size:9px; padding:6px 8px; border:1px solid var(--line); border-radius:7px; }
.metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:14px; }
.metrics article { padding:10px; border:1px solid var(--line); border-radius:11px; background:var(--surface); }
.metrics small { display:block; color:var(--text-subtle); font-size:8px; }
.metrics strong { display:block; margin-top:3px; font-size:12px; white-space:nowrap; }
.metrics em { display:block; margin-top:3px; color:var(--success-color); font-size:8px; font-style:normal; font-weight:800; }
.chart-card { margin-top:10px; padding:12px; border:1px solid var(--line); border-radius:12px; }
.chart-card__head { display:flex; justify-content:space-between; align-items:center; font-size:10px; }
.chart-card__head span { color:var(--text-subtle); font-size:8px; }
.chart-card svg { width:100%; height:118px; margin-top:4px; }
.preview-bottom { display:grid; grid-template-columns:1fr 1.35fr; gap:10px; margin-top:10px; }
.profit-card,.top-card { padding:12px; border:1px solid var(--line); border-radius:12px; min-height:110px; }
.profit-card { display:grid; grid-template-columns:52px 1fr; gap:7px 10px; align-items:center; }
.profit-card small { grid-column:1/-1; color:var(--text-subtle); font-size:8px; }
.profit-card strong { font-size:9px; line-height:1.35; }
.donut { width:46px; height:46px; border-radius:50%; background:conic-gradient(var(--secondary-color) 0 40%,var(--success-color) 40% 66%,var(--warning-color) 66% 83%,var(--border-color) 83%); position:relative; }
.donut:after { content:""; position:absolute; inset:10px; border-radius:50%; background:var(--surface); }
.top-card small { color:var(--text-subtle); font-size:8px; }
.top-card p { display:flex; justify-content:space-between; gap:8px; margin-top:8px; font-size:8px; }
.top-card span { color:var(--muted); }
.top-card b { white-space:nowrap; }

.section { padding: 96px 0; }
.section--soft { background: var(--soft); border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
.section-heading { max-width:780px; margin-bottom:42px; }
.section-heading h2,.final-cta h2 { margin-top:8px; color:var(--ink); font-size:clamp(32px,4vw,48px); letter-spacing:-.04em; line-height:1.08; }
.section-heading > p:last-child { margin-top:14px; color:var(--muted); font-size:16px; line-height:1.7; }
.section-heading--split { max-width:none; display:grid; grid-template-columns:1fr .7fr; gap:60px; align-items:end; }
.section-heading--split > p { margin:0 0 4px; }

.problem-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.problem-card { padding:24px; min-height:210px; border:1px solid var(--line); border-radius:18px; background:linear-gradient(145deg,var(--surface),color-mix(in srgb, var(--surface) 94%, var(--pink) 6%)); }
.problem-card__icon { width:42px; height:42px; display:grid; place-items:center; border-radius:12px; color:var(--danger-color); background:color-mix(in srgb, var(--pink) 12%, var(--surface)); font-size:20px; font-weight:900; }
.problem-card h3,.feature-card h3,.roadmap-grid h3,.steps h3 { margin-top:18px; font-size:17px; letter-spacing:-.02em; }
.problem-card p,.feature-card p,.roadmap-grid p,.steps p { margin-top:9px; color:var(--muted); font-size:14px; line-height:1.65; }

.feature-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
.feature-card { display:flex; gap:14px; padding:20px; border:1px solid var(--line); border-radius:16px; background:var(--surface); box-shadow:var(--shadow-sm); }
.feature-card > span { flex:0 0 38px; width:38px; height:38px; display:grid; place-items:center; border-radius:11px; color:var(--secondary-color); background:color-mix(in srgb, var(--secondary-color) 12%, var(--surface)); font-weight:900; }
.feature-card h3 { margin-top:2px; }
.feature-card p { margin-top:6px; }

.proof { padding-top:20px; }
.proof__panel { padding:36px; display:grid; grid-template-columns:.6fr 1fr; gap:40px; align-items:center; border-radius:26px; background:linear-gradient(135deg,#17133f,#4e40cd 66%,#6c5cff); color:#fff; box-shadow:0 30px 80px rgba(56,47,143,.24); }
.proof__panel h2 { margin-top:8px; font-size:38px; letter-spacing:-.04em; }
.proof__panel .section-kicker { color:#cfcaff; }
.proof__items { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }
.proof__items article { padding:16px; display:flex; gap:12px; align-items:center; border:1px solid rgba(255,255,255,.13); border-radius:14px; background:rgba(255,255,255,.07); }
.proof__items strong { color:#cfcaff; font-size:13px; }
.proof__items span { font-size:13px; font-weight:700; }

.steps__grid { display:grid; grid-template-columns:repeat(3,1fr); gap:24px; }
.steps article { position:relative; padding:28px; border-top:1px solid var(--line); }
.steps article b { width:42px; height:42px; display:grid; place-items:center; border-radius:50%; color:#fff; background:linear-gradient(135deg,#635bff,#8b5cf6); box-shadow:0 10px 22px rgba(99,91,255,.25); }
.center-cta { margin-top:34px; text-align:center; }

.roadmap { background:var(--soft); border-top:1px solid var(--line); border-bottom:1px solid var(--line); }
.roadmap-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.roadmap-grid article { padding:22px; border:1px solid var(--line); border-radius:17px; background:color-mix(in srgb, var(--surface) 94%, transparent); }
.roadmap-grid article > span { display:inline-flex; padding:5px 8px; border-radius:999px; color:var(--success-color); background:color-mix(in srgb, var(--success-color) 12%, var(--surface)); font-size:9px; font-weight:900; text-transform:uppercase; letter-spacing:.08em; }

.faq__grid { display:grid; grid-template-columns:.45fr 1fr; gap:70px; align-items:start; }
.faq__intro h2 { margin-top:8px; font-size:42px; letter-spacing:-.04em; }
.faq__intro > p:last-of-type { margin-top:12px; color:var(--muted); line-height:1.7; }
.text-link { margin-top:20px; padding:0; border:0; color:var(--secondary-color); background:transparent; font-weight:800; cursor:pointer; }
.faq__items details { border-bottom:1px solid var(--line); }
.faq__items summary { padding:20px 0; display:flex; justify-content:space-between; gap:20px; list-style:none; font-weight:800; cursor:pointer; }
.faq__items summary::-webkit-details-marker { display:none; }
.faq__items summary span { color:var(--secondary-color); font-size:20px; }
.faq__items details[open] summary span { transform:rotate(45deg); }
.faq__items details p { padding:0 0 20px; color:var(--muted); line-height:1.7; }

.final-cta { padding:34px 0 70px; }
.final-cta__panel { padding:44px; display:flex; justify-content:space-between; gap:36px; align-items:center; border-radius:28px; color:#fff; background:linear-gradient(115deg,#5045e5,#6d5dfc 55%,#a14ee9); box-shadow:0 28px 70px rgba(87,72,221,.25); }
.final-cta .section-kicker { color:#dcd8ff; }
.final-cta h2 { max-width:760px; color:#fff; font-size:40px; }
.final-cta p:last-child { max-width:700px; margin-top:12px; color:#ebe9ff; line-height:1.65; }
.final-cta .cta { flex:0 0 auto; }

.landing-footer { border-top:1px solid var(--line); background:var(--surface); }
.landing-footer__inner { min-height:90px; display:flex; justify-content:space-between; gap:24px; align-items:center; }
.landing-footer__brand { display:flex; align-items:center; gap:7px; }
.landing-footer__brand span { padding:6px 8px; border-radius:8px; color:#fff; background:#655cf3; font-size:11px; font-weight:900; }
.landing-footer nav { display:flex; gap:20px; flex-wrap:wrap; color:var(--muted); font-size:12px; font-weight:700; }

@media (max-width: 1050px) {
  .hero__grid { grid-template-columns:1fr; }
  .hero__copy { max-width:760px; }
  .product-preview { transform:none; }
  .feature-grid { grid-template-columns:repeat(2,1fr); }
  .problem-grid { grid-template-columns:repeat(2,1fr); }
  .proof__panel { grid-template-columns:1fr; }
}
@media (max-width: 760px) {
  .landing-shell { width:min(100% - 24px,1240px); }
  .hero { padding:52px 0 64px; }
  .hero h1 { font-size:42px; }
  .hero__lead { font-size:16px; }
  .hero__actions .cta { width:100%; }
  .hero__meta { gap:9px 16px; }
  .product-preview { border-radius:18px; overflow-x:auto; }
  .preview-layout { min-width:720px; }
  .section { padding:72px 0; }
  .section-heading--split { grid-template-columns:1fr; gap:10px; }
  .problem-grid,.feature-grid,.roadmap-grid,.steps__grid { grid-template-columns:1fr; }
  .problem-card { min-height:auto; }
  .faq__grid { grid-template-columns:1fr; gap:24px; }
  .proof__panel { padding:28px 20px; }
  .proof__items { grid-template-columns:1fr; }
  .final-cta__panel { padding:30px 22px; flex-direction:column; align-items:flex-start; }
  .final-cta .cta { width:100%; }
  .landing-footer__inner { padding:24px 0; align-items:flex-start; flex-direction:column; }
}
</style>
