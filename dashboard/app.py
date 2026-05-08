"""
DrugCheck Dashboard — аналитика для владельцев сервиса и администраторов.
Доступен по http://localhost:8501
"""
import os
import httpx
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="DrugCheck Analytics",
    page_icon="💊",
    layout="wide",
)

# ──────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────
def login(email: str, password: str) -> str | None:
    try:
        resp = httpx.post(
            f"{API_URL}/api/v1/auth/login",
            data={"username": email, "password": password},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
    except Exception:
        pass
    return None


def api_get(path: str, token: str) -> dict | list | None:
    try:
        resp = httpx.get(
            f"{API_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None

# ──────────────────────────────────────────────────────────
# Login / Register screen
# ──────────────────────────────────────────────────────────
def register(email: str, password: str, full_name: str) -> tuple[bool, str]:
    try:
        resp = httpx.post(
            f"{API_URL}/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
            timeout=5,
        )
        if resp.status_code == 201:
            return True, ""
        return False, resp.json().get("detail", "Ошибка регистрации")
    except Exception as e:
        return False, str(e)


if not st.session_state.token:
    st.title("💊 DrugCheck")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_register = st.tabs(["Войти", "Регистрация"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="user@example.com", key="li_email")
                password = st.text_input("Пароль", type="password", key="li_pass")
                submitted = st.form_submit_button("Войти", use_container_width=True)
                if submitted:
                    token = login(email, password)
                    if token:
                        st.session_state.token = token
                        user = api_get("/auth/me", token)
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Неверный email или пароль")

        with tab_register:
            with st.form("register_form"):
                reg_name = st.text_input("Имя", placeholder="Иван Иванов")
                reg_email = st.text_input("Email", placeholder="user@example.com", key="reg_email")
                reg_pass = st.text_input("Пароль", type="password", key="reg_pass")
                reg_submitted = st.form_submit_button("Создать аккаунт", use_container_width=True, type="primary")
                if reg_submitted:
                    if not reg_name or not reg_email or not reg_pass:
                        st.error("Заполните все поля")
                    elif len(reg_pass) < 8:
                        st.error("Пароль должен содержать минимум 8 символов")
                    else:
                        ok, err = register(reg_email, reg_pass, reg_name)
                        if ok:
                            st.success("Аккаунт создан! Войдите на вкладке «Войти».")
                        else:
                            st.error(err)
    st.stop()

token = st.session_state.token
user = st.session_state.user or {}

# ──────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 💊 DrugCheck")
    st.markdown(f"**{user.get('email', '')}**")
    st.markdown(f"Уровень: `{user.get('loyalty_level', 'bronze').upper()}`")
    st.markdown(f"Баланс: **{user.get('balance', 0)} кредитов**")
    st.divider()

    page = st.radio("Раздел", [
        "📊 Главная",
        "💉 Проверка взаимодействий",
        "📜 История проверок",
        "💳 Биллинг",
    ] + (["⚙️ Администрирование"] if user.get("is_admin") else []))

    if st.button("Выйти", use_container_width=True):
        st.session_state.token = None
        st.session_state.user = None
        st.rerun()

# ──────────────────────────────────────────────────────────
# Главная — личная статистика
# ──────────────────────────────────────────────────────────
if page == "📊 Главная":
    st.title("📊 Ваша статистика")

    balance_data = api_get("/billing/balance", token) or {}
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Баланс", f"{balance_data.get('balance', 0)} кр.")
    col2.metric("Уровень лояльности", balance_data.get("loyalty_level", "bronze").capitalize())
    col3.metric("Скидка", f"{balance_data.get('discount_percent', 0)}%")
    col4.metric("Стоимость проверки", f"{balance_data.get('check_cost_with_discount', 5)} кр.")

    st.divider()

    loyalty_levels = {"bronze": 0, "silver": 50, "gold": 200}
    current = balance_data.get("monthly_checks", 0)
    current_level = balance_data.get("loyalty_level", "bronze")
    next_threshold = 200 if current_level == "silver" else (50 if current_level == "bronze" else None)

    if next_threshold:
        progress = min(current / next_threshold, 1.0)
        st.subheader(f"Прогресс до следующего уровня")
        st.progress(progress)
        remaining = max(next_threshold - current, 0)
        next_level = "silver" if current_level == "bronze" else "gold"
        st.caption(f"Ещё {remaining} проверок до уровня **{next_level.upper()}**")
    else:
        st.success("🥇 Вы на максимальном уровне — Gold! Скидка 15% на все проверки.")

    st.subheader("Последние транзакции")
    txs = api_get("/billing/transactions?limit=10", token)
    if txs:
        df = pd.DataFrame(txs)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d.%m %H:%M")
        df["type_label"] = df["type"].map({"debit": "➖ Списание", "credit": "➕ Начисление", "topup": "💰 Пополнение"})
        st.dataframe(
            df[["created_at", "type_label", "amount", "balance_after", "description"]].rename(columns={
                "created_at": "Дата", "type_label": "Тип", "amount": "Сумма",
                "balance_after": "Баланс после", "description": "Описание",
            }),
            use_container_width=True, hide_index=True,
        )

# ──────────────────────────────────────────────────────────
# Проверка взаимодействий
# ──────────────────────────────────────────────────────────
elif page == "💉 Проверка взаимодействий":
    st.title("💉 Проверка лекарственных взаимодействий")

    balance_data = api_get("/billing/balance", token) or {}
    cost = balance_data.get("check_cost_with_discount", 5)
    st.info(f"Стоимость проверки: **{cost} кредитов** (уровень {balance_data.get('loyalty_level','bronze').upper()})")

    with st.form("check_form"):
        drugs_input = st.text_area(
            "Введите названия препаратов (каждый с новой строки)",
            placeholder="Нолипрел\nМетформин\nАторвастатин\nАспирин",
            height=150,
        )
        submitted = st.form_submit_button("Проверить взаимодействия", use_container_width=True, type="primary")

    if submitted and drugs_input.strip():
        drugs = [d.strip() for d in drugs_input.strip().splitlines() if d.strip()]
        if len(drugs) < 2:
            st.error("Введите минимум 2 препарата")
        else:
            with st.spinner("Отправляю запрос..."):
                try:
                    resp = httpx.post(
                        f"{API_URL}/api/v1/interactions/check",
                        json={"drugs": drugs},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    if resp.status_code == 202:
                        check = resp.json()
                        check_id = check["check_id"]
                        st.success(f"Проверка запущена (ID: {check_id}). Получаю результат...")

                        import time
                        for _ in range(15):
                            time.sleep(1)
                            result = api_get(f"/interactions/check/{check_id}", token)
                            if result and result.get("status") in ("completed", "failed"):
                                break

                        if result and result.get("status") == "completed":
                            interactions = result.get("interactions") or []
                            found = len(interactions)

                            if found == 0:
                                st.success("✅ Опасных взаимодействий не обнаружено!")
                            else:
                                st.warning(f"⚠️ Найдено {found} взаимодействий")

                            severity_colors = {
                                "contraindicated": "🔴",
                                "severe":          "🟠",
                                "moderate":        "🟡",
                                "mild":            "🟢",
                            }

                            for inter in interactions:
                                icon = severity_colors.get(inter.get("severity", ""), "⚪")
                                with st.expander(f"{icon} {inter['drug_a']} + {inter['drug_b']} — {inter.get('severity','').upper()}"):
                                    st.write(f"**Описание:** {inter.get('description','')}")
                                    st.write(f"**Рекомендация:** {inter.get('recommendation','')}")
                                    st.progress(inter.get("severity_score", 0))

                        elif result and result.get("status") == "failed":
                            st.error(f"Ошибка: {result.get('error_message','')}")
                    elif resp.status_code == 402:
                        st.error("Недостаточно кредитов. Пополните баланс.")
                    else:
                        st.error(f"Ошибка API: {resp.text}")
                except Exception as e:
                    st.error(f"Ошибка подключения: {e}")

# ──────────────────────────────────────────────────────────
# История проверок
# ──────────────────────────────────────────────────────────
elif page == "📜 История проверок":
    st.title("📜 История проверок")
    history = api_get("/interactions/history?limit=50", token)
    if history:
        df = pd.DataFrame(history)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d.%m.%Y %H:%M")
        df["drugs"] = df["drugs_input"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
        df["status_label"] = df["status"].map({
            "completed": "✅ Готово", "pending": "⏳ Ожидание",
            "processing": "🔄 Обработка", "failed": "❌ Ошибка",
        })
        st.dataframe(
            df[["created_at", "drugs", "status_label", "interactions_found", "cost"]].rename(columns={
                "created_at": "Дата", "drugs": "Препараты", "status_label": "Статус",
                "interactions_found": "Найдено взаимодействий", "cost": "Стоимость",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Проверок пока нет.")

# ──────────────────────────────────────────────────────────
# Биллинг
# ──────────────────────────────────────────────────────────
elif page == "💳 Биллинг":
    st.title("💳 Пополнение баланса")
    balance_data = api_get("/billing/balance", token) or {}
    st.metric("Текущий баланс", f"{balance_data.get('balance', 0)} кредитов")

    st.subheader("Купить кредиты")
    packages = {
        "50 кредитов — 199 ₽":  199,
        "150 кредитов — 499 ₽": 499,
        "500 кредитов — 1490 ₽": 1490,
    }
    selected = st.radio("Выберите пакет", list(packages.keys()))
    amount_rub = packages[selected]

    if st.button("Перейти к оплате", type="primary", use_container_width=True):
        try:
            resp = httpx.post(
                f"{API_URL}/api/v1/billing/payment/create",
                json={"amount_rub": amount_rub},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("test_mode"):
                    confirm_resp = httpx.get(data["confirmation_url"], timeout=5)
                    if confirm_resp.status_code == 200:
                        st.success(f"Баланс пополнен! +{data['credits']} кредитов (тестовый режим)")
                        st.rerun()
                    else:
                        st.error("Ошибка при начислении кредитов")
                else:
                    st.markdown(
                        f"[Оплатить {amount_rub} ₽ через ЮКасса]({data['confirmation_url']})",
                        unsafe_allow_html=False,
                    )
                    st.info("После оплаты кредиты появятся на балансе автоматически.")
            else:
                st.error(f"Ошибка: {resp.text}")
        except Exception as e:
            st.error(f"Ошибка подключения: {e}")

# ──────────────────────────────────────────────────────────
# Администрирование
# ──────────────────────────────────────────────────────────
elif page == "⚙️ Администрирование":
    st.title("⚙️ Панель администратора")
    stats = api_get("/admin/stats", token) or {}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего пользователей", stats.get("total_users", 0))
    col2.metric("Всего проверок", stats.get("total_checks", 0))
    col3.metric("Завершено успешно", stats.get("completed_checks", 0))
    col4.metric("Доход (кредиты)", stats.get("total_revenue_credits", 0))

    loyalty_dist = stats.get("loyalty_distribution", {})
    if loyalty_dist:
        st.subheader("Распределение по уровням лояльности")
        fig = px.pie(
            names=list(loyalty_dist.keys()),
            values=list(loyalty_dist.values()),
            color_discrete_map={"bronze": "#CD7F32", "silver": "#C0C0C0", "gold": "#FFD700"},
            hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Пользователи")
    users = api_get("/admin/users?limit=50", token)
    if users:
        df = pd.DataFrame(users)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%d.%m.%Y")
        st.dataframe(
            df[["id", "email", "loyalty_level", "balance", "monthly_checks", "created_at"]].rename(columns={
                "id": "ID", "email": "Email", "loyalty_level": "Уровень",
                "balance": "Баланс", "monthly_checks": "Проверок/мес", "created_at": "Регистрация",
            }),
            use_container_width=True, hide_index=True,
        )
