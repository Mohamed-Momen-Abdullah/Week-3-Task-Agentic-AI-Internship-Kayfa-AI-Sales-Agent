import sys
from pathlib import Path

# Add the root project directory to Python's import path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from database.mongo import get_all_tickets
from app.utils import inject_custom_css, render_header, require_password

st.set_page_config(
    page_title="Kayfa CRM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- THEME, AUTH, HEADER ---
c = inject_custom_css()

if not require_password("the Kayfa CRM dashboard"):
    st.stop()

render_header(
    "CRM Lead Tickets",
    "Review captured leads and follow up with prospective learners",
)

tickets = get_all_tickets()

if not tickets:
    st.info("No leads captured yet. Go back to the Chat Agent and try matching a lead!")
else:
    st.metric("Total Qualified Leads", len(tickets))
    st.divider()

    for t in tickets:
        name = t.get("customer_name", "غير معروف")
        timestamp = t.get("timestamp", "N/A")
        signals = t.get("buying_signals", "ساخن")
        lead_id = str(t.get('_id'))[-6:].upper()
        contact = t.get('contact_info', '')
        city = t.get('city', '')
        dialect = t.get('language_dialect', '')
        products = t.get('products_of_interest', '')
        goal = t.get('goal', '')
        level = t.get('current_level', '')
        objections = t.get('objections', '')
        summary = t.get('arabic_summary', '')
        next_action = t.get('next_action', '')

        # All colors come from the same theme tokens inject_custom_css() used,
        # so this card always matches the page background, dark or light.
        card_content = f"""
        <div dir="rtl" style="background-color: {c['card_bg']}; border: 1px solid {c['card_border']}; border-radius: 12px; padding: 20px; margin-bottom: 20px; text-align: right; font-family: sans-serif; color: {c['text']};">
            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid {c['card_border']}; padding-bottom: 8px; margin-bottom: 12px;">
                <span style="background-color: {c['danger_bg']}; color: {c['danger_text']}; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">{signals}</span>
                <span style="color: {c['text_muted']}; font-size: 14px; font-weight: bold;">LEAD-{lead_id}</span>
            </div>
            <p style="margin: 6px 0;"><strong>الاسم:</strong> {name}</p>
            <p style="margin: 6px 0;"><strong>رقم التواصل:</strong> <span dir="ltr">{contact}</span></p>
            <p style="margin: 6px 0;"><strong>المدينة:</strong> {city}</p>
            <p style="margin: 6px 0;"><strong>اللغة / اللهجة:</strong> {dialect}</p>
            <p style="margin: 6px 0; color: {c['primary']};"><strong>المنتجات محل الاهتمام:</strong> {products}</p>
            <p style="margin: 6px 0;"><strong>الهدف:</strong> {goal}</p>
            <p style="margin: 6px 0;"><strong>المستوى الحالي:</strong> {level}</p>
            <p style="margin: 6px 0; color: {c['warning_text']};"><strong>الاعتراضات:</strong> {objections}</p>
            <div style="background: {c['bg']}; padding: 10px; border-radius: 6px; margin-top: 10px; border-left: 4px solid {c['primary']};">
                <strong>ملخّص المحادثة:</strong>
                <p style="margin: 4px 0; line-height: 1.5; color: {c['text']};">{summary}</p>
            </div>
            <p style="margin: 10px 0 0 0; color: {c['success_text']};"><strong>الإجراء التالي:</strong> {next_action}</p>
            <p style="margin: 8px 0 0 0; color: {c['text_muted']}; font-size: 12px;" dir="ltr">التاريخ: {timestamp}</p>
        </div>
        """
        st.markdown(card_content, unsafe_allow_html=True)