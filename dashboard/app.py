import os
import httpx
import streamlit as st
import pandas as pd
import plotly.express as px

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="DrugCheck Analytics",
    page_icon="💊",
    layout="wide",
)

# ──────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────
def login(email, password):
    try:
        resp = httpx.post(
            f"{API_URL}/api/v1/auth/login",
            data={"username": email, "password": password},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
        # print("login failed:", resp.status_code, resp.text)
    except Exception as e:
        print("login error:", e)
    return None


def api_get(path, token):
    try:
        resp = httpx.get(
            f"{API_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print("api_get error:", e)
    return None


def api_post(path, token, data):
    try:
        return httpx.post(
            f"{API_URL}/api/v1{path}",
            json=data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except Exception as e:
        print("api_post error:", e)
    return None


def api_patch(path, token, data):
    try:
        return httpx.patch(
            f"{API_URL}/api/v1{path}",
            json=data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except Exception as e:
        print("api_patch error:", e)
    return None


def api_delete(path, token):
    try:
        return httpx.delete(
            f"{API_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except Exception as e:
        print("api_delete error:", e)
    return None


# ──────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "sel_patient" not in st.session_state:
    st.session_state.sel_patient = None
if "patient_form" not in st.session_state:
    st.session_state.patient_form = None   # None | "add" | <patient_dict>
if "patient_del_confirm" not in st.session_state:
    st.session_state.patient_del_confirm = None
if "drug_check_patient" not in st.session_state:
    st.session_state.drug_check_patient = None

# ──────────────────────────────────────────────────────────
# Login / Register screen
# ──────────────────────────────────────────────────────────
def register(email, password, full_name):
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
        "🧑‍⚕️ Пациенты",
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

    current = balance_data.get("monthly_checks", 0)
    current_level = balance_data.get("loyalty_level", "bronze")
    if current_level == "bronze":
        next_threshold = 50
    elif current_level == "silver":
        next_threshold = 200
    else:
        next_threshold = None

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
# Пациенты
# ──────────────────────────────────────────────────────────
elif page == "🧑‍⚕️ Пациенты":

    # ── helpers ──────────────────────────────────────────
    RISK_META = {
        "normal":   ("🟢", "Норма",                    "СКФ ≥ 60 — коррекция дозы не нужна"),
        "mild":     ("🟡", "Лёгкое снижение",          "СКФ 45–59 — мониторинг"),
        "moderate": ("🟠", "Умеренная НПН",             "СКФ 30–44 — требуется коррекция доз"),
        "severe":   ("🔴", "Тяжёлая НПН",              "СКФ 15–29 — обязательная коррекция"),
        "failure":  ("🔴", "Почечная недостаточность",  "СКФ < 15 — большинство нефротоксичных противопоказаны"),
    }

    def _gfr_risk(gfr):
        if gfr is None:
            return None
        if gfr >= 60: return "normal"
        if gfr >= 45: return "mild"
        if gfr >= 30: return "moderate"
        if gfr >= 15: return "severe"
        return "failure"

    def _risk_badge(gfr):
        risk = _gfr_risk(gfr)
        if risk is None:
            return "—"
        icon, label, _ = RISK_META[risk]
        return f"{icon} {label}"

    def _patient_form(title, defaults=None):
        d = defaults or {}
        with st.form("patient_form", border=True):
            st.markdown(f"#### {title}")
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input("Имя пациента *", value=d.get("name", ""),
                                     placeholder="Иванов Иван Иванович")
                age_val = d.get("age") or 0
                age = st.number_input("Возраст (лет)", min_value=0, max_value=120,
                                      value=int(age_val), step=1)
            with c2:
                w_val = float(d.get("weight_kg") or 0)
                weight = st.number_input("Вес (кг)", min_value=0.0, max_value=500.0,
                                         value=w_val, step=0.5)
                gfr_val = float(d.get("gfr") or 0)
                gfr = st.number_input("СКФ (мл/мин/1.73м²)", min_value=0.0, max_value=200.0,
                                      value=gfr_val, step=1.0,
                                      help="Скорость клубочковой фильтрации. 0 = не указано.")
            with c3:
                diag_str = ", ".join(d.get("diagnoses", []))
                diagnoses_input = st.text_input("Диагнозы МКБ-10 (через запятую)",
                                                value=diag_str,
                                                placeholder="I10, E11.9, N18.3")
                notes = st.text_area("Примечания", value=d.get("notes", "") or "",
                                     height=88, placeholder="Аллергии, особенности лечения…")

            sc, cc = st.columns(2)
            saved   = sc.form_submit_button("💾 Сохранить", use_container_width=True, type="primary")
            cancelled = cc.form_submit_button("Отмена",     use_container_width=True)

        if cancelled:
            st.session_state.patient_form = None
            st.session_state.sel_patient  = None
            st.rerun()

        if saved:
            if not name.strip():
                st.error("Укажите имя пациента")
                st.stop()
            diagnoses = [x.strip().upper() for x in diagnoses_input.split(",") if x.strip()]
            return {
                "name":       name.strip(),
                "age":        int(age) if age > 0 else None,
                "weight_kg":  float(weight) if weight > 0 else None,
                "gfr":        float(gfr) if gfr > 0 else None,
                "diagnoses":  diagnoses,
                "notes":      notes.strip() or None,
            }
        return None

    # ── header ───────────────────────────────────────────
    hc1, hc2 = st.columns([5, 1])
    hc1.title("🧑‍⚕️ Пациенты")
    if hc2.button("＋ Добавить", type="primary", use_container_width=True):
        st.session_state.patient_form = "add"
        st.session_state.sel_patient  = None
        st.session_state.patient_del_confirm = None

    # ── add form ─────────────────────────────────────────
    if st.session_state.patient_form == "add":
        payload = _patient_form("Новый пациент")
        if payload is not None:
            resp = api_post("/patients", token, payload)
            if resp and resp.status_code == 201:
                st.success("Пациент добавлен!")
                st.session_state.patient_form = None
                st.rerun()
            else:
                st.error(f"Ошибка: {resp.text if resp else 'нет ответа'}")

    # ── edit form ────────────────────────────────────────
    elif isinstance(st.session_state.patient_form, dict):
        editing = st.session_state.patient_form
        payload = _patient_form(f"Редактировать — {editing['name']}", defaults=editing)
        if payload is not None:
            resp = api_patch(f"/patients/{editing['id']}", token, payload)
            if resp and resp.status_code == 200:
                st.success("Данные обновлены!")
                st.session_state.patient_form = None
                st.session_state.sel_patient  = resp.json()
                st.rerun()
            else:
                st.error(f"Ошибка: {resp.text if resp else 'нет ответа'}")

    st.divider()

    # ── load & search ─────────────────────────────────────
    patients = api_get("/patients?limit=200", token) or []
    search = st.text_input("🔍 Поиск", placeholder="Имя, МКБ-код диагноза…", label_visibility="collapsed")
    if search:
        q = search.lower()
        patients = [p for p in patients
                    if q in p["name"].lower()
                    or any(q in d.lower() for d in p.get("diagnoses", []))]

    if not patients and not search:
        st.info("Пациентов пока нет. Нажмите «＋ Добавить».")

    # ── patient list ──────────────────────────────────────
    for p in patients:
        is_selected = st.session_state.sel_patient and st.session_state.sel_patient.get("id") == p["id"]
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 1, 3, 2])
            with c1:
                st.markdown(f"**{p['name']}**")
                if p.get("diagnoses"):
                    st.caption("  ".join(f"`{d}`" for d in p["diagnoses"][:6]))
            with c2:
                st.markdown(f"{p['age'] or '—'} лет")
                if p.get("weight_kg"):
                    st.caption(f"{p['weight_kg']} кг")
            with c3:
                if p.get("gfr") is not None:
                    st.markdown(f"СКФ **{p['gfr']}** → {_risk_badge(p['gfr'])}")
                else:
                    st.caption("СКФ не указан")
            with c4:
                ba, bb, bc = st.columns(3)
                if ba.button("👁", key=f"v_{p['id']}", help="Открыть карту",
                             type="primary" if is_selected else "secondary"):
                    st.session_state.sel_patient = None if is_selected else p
                    st.session_state.patient_form = None
                    st.session_state.patient_del_confirm = None
                    st.session_state.drug_check_patient = None
                    st.rerun()
                if bb.button("✏️", key=f"e_{p['id']}", help="Редактировать"):
                    st.session_state.patient_form = p
                    st.session_state.sel_patient  = None
                    st.rerun()
                if bc.button("🗑", key=f"d_{p['id']}", help="Удалить"):
                    st.session_state.patient_del_confirm = p["id"]
                    st.session_state.sel_patient = None
                    st.rerun()

        # ── delete confirm ────────────────────────────────
        if st.session_state.patient_del_confirm == p["id"]:
            with st.container(border=True):
                st.warning(f"Удалить пациента **{p['name']}**? Это действие нельзя отменить.")
                yc, nc = st.columns(2)
                if yc.button("Да, удалить", key=f"yd_{p['id']}", type="primary"):
                    api_delete(f"/patients/{p['id']}", token)
                    st.session_state.patient_del_confirm = None
                    st.session_state.sel_patient = None
                    st.rerun()
                if nc.button("Отмена", key=f"nd_{p['id']}"):
                    st.session_state.patient_del_confirm = None
                    st.rerun()

        # ── patient detail card ───────────────────────────
        if is_selected:
            sel = st.session_state.sel_patient
            with st.container(border=True):
                dc1, dc2 = st.columns([3, 2])
                with dc1:
                    st.markdown(f"### 👤 {sel['name']}")
                    info_rows = []
                    if sel.get("age"):        info_rows.append(f"**Возраст:** {sel['age']} лет")
                    if sel.get("weight_kg"):  info_rows.append(f"**Вес:** {sel['weight_kg']} кг")
                    if sel.get("notes"):      info_rows.append(f"**Примечания:** {sel['notes']}")
                    for row in info_rows:
                        st.markdown(row)
                    if sel.get("diagnoses"):
                        st.markdown("**Диагнозы:** " + "  ".join(f"`{d}`" for d in sel["diagnoses"]))

                with dc2:
                    gfr = sel.get("gfr")
                    if gfr is not None:
                        risk = _gfr_risk(gfr)
                        icon, label, note = RISK_META[risk]
                        st.markdown(f"#### СКФ: {gfr} мл/мин/1.73м²")
                        st.markdown(f"## {icon} {label}")
                        st.caption(note)
                    else:
                        st.markdown("#### СКФ не указан")
                        st.caption("Добавьте СКФ для оценки почечного риска")

                st.divider()

                # inline drug check
                dcp_key = f"dcp_{sel['id']}"
                show_check = st.session_state.drug_check_patient == sel["id"]
                if st.button(
                    "💊 Проверить взаимодействие препаратов" if not show_check else "▲ Скрыть",
                    key=f"show_dcp_{sel['id']}",
                ):
                    st.session_state.drug_check_patient = None if show_check else sel["id"]
                    st.rerun()

                if show_check:
                    with st.form(dcp_key):
                        st.markdown("**Введите препараты пациента (каждый с новой строки):**")
                        drugs_txt = st.text_area(
                            "Препараты", height=120,
                            placeholder="Нолипрел\nМетформин\nАторвастатин",
                            label_visibility="collapsed",
                        )
                        run_check = st.form_submit_button("▶ Проверить", type="primary",
                                                          use_container_width=True)
                    if run_check:
                        drugs = [d.strip() for d in drugs_txt.splitlines() if d.strip()]
                        if len(drugs) < 2:
                            st.error("Введите минимум 2 препарата")
                        else:
                            with st.spinner("Проверяю…"):
                                resp = api_post("/interactions/check", token, {"drugs": drugs})
                            if resp and resp.status_code == 202:
                                check_id = resp.json()["id"]
                                import time
                                result = None
                                for _ in range(20):
                                    time.sleep(1)
                                    result = api_get(f"/interactions/check/{check_id}", token)
                                    if result and result.get("status") in ("completed", "failed"):
                                        break
                                if result and result.get("status") == "completed":
                                    interactions = result.get("result") or []
                                    if not interactions:
                                        st.success("✅ Опасных взаимодействий не обнаружено")
                                    else:
                                        SEV_ICON = {"contraindicated": "🔴", "severe": "🟠",
                                                    "moderate": "🟡", "mild": "🟢"}
                                        st.warning(f"⚠️ Найдено взаимодействий: {len(interactions)}")
                                        for ix in interactions:
                                            sev = ix.get("severity", "")
                                            ico = SEV_ICON.get(sev, "⚪")
                                            with st.expander(
                                                f"{ico} {ix['drug_a']} + {ix['drug_b']} — {sev.upper()}"
                                            ):
                                                st.write(f"**Описание:** {ix.get('description','')}")
                                                st.write(f"**Рекомендация:** {ix.get('recommendation','')}")
                                                if gfr and gfr < 60 and sev in ("severe", "contraindicated"):
                                                    st.error("⚠️ У пациента снижена функция почек — особая осторожность!")
                                elif result and result.get("status") == "failed":
                                    st.error(f"Ошибка: {result.get('error_message','')}")
                            elif resp and resp.status_code == 402:
                                st.error("Недостаточно кредитов. Пополните баланс.")
                            else:
                                st.error("Ошибка запроса")

    st.divider()
    st.caption(f"Всего пациентов: {len(patients)}")

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
                        check_id = check["id"]
                        st.success(f"Проверка запущена (ID: {check_id}). Получаю результат...")

                        import time
                        for _ in range(15):
                            time.sleep(1)
                            result = api_get(f"/interactions/check/{check_id}", token)
                            if result and result.get("status") in ("completed", "failed"):
                                break

                        if result and result.get("status") == "completed":
                            interactions = result.get("result") or []
                            found = len(interactions)

                            if found == 0:
                                st.success("✅ Опасных взаимодействий не обнаружено!")
                            else:
                                st.warning(f"⚠️ Найдено {found} взаимодействий")

                            for inter in interactions:
                                sev = inter.get("severity", "")
                                if sev == "contraindicated":
                                    icon = "🔴"
                                elif sev == "severe":
                                    icon = "🟠"
                                elif sev == "moderate":
                                    icon = "🟡"
                                elif sev == "mild":
                                    icon = "🟢"
                                else:
                                    icon = "⚪"
                                with st.expander(f"{icon} {inter['drug_a']} + {inter['drug_b']} — {sev.upper()}"):
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
