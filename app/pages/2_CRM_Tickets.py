import sys
from pathlib import Path

# Add the root project directory to Python's import path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from database.mongo import get_all_tickets

st.set_page_config(page_title="Kayfa CRM Dashboard", page_icon="📊", layout="wide")

import streamlit as st

def check_password():
    """Returns `True` if the user has the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            # Delete the password from session state for security
            del st.session_state["password"]  
        else:
            st.session_state["password_correct"] = False

    # If the password hasn't been verified yet
    if "password_correct" not in st.session_state:
        st.text_input("Please enter the password to access the Kayfa CRM", type="password", on_change=password_entered, key="password")
        return False
        
    # If the user entered the wrong password
    elif not st.session_state["password_correct"]:
        st.text_input("Please enter the password to access the Kayfa CRM", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect.")
        return False
        
    # Password is correct
    else:
        return True

# --- MAIN APP EXECUTION ---
if not check_password():
    st.stop()  # Do not run anything below this line if password fails

# [The rest of your chat UI and agent logic goes down here as normal]

st.title("📊 CRM Lead Tickets")
st.markdown("Review captured leads and follow up with prospective learners.")

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

        card_content = f"""
        <div dir="rtl" style="background-color: #f8f9fc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 20px; text-align: right; font-family: sans-serif;">
            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 12px;">
                <span style="background-color: #ffebee; color: #c62828; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">{signals}</span>
                <span style="color: #64748b; font-size: 14px; font-weight: bold;">LEAD-{lead_id}</span>
            </div>
            <p style="margin: 6px 0;"><strong>الاسم:</strong> {name}</p>
            <p style="margin: 6px 0;"><strong>رقم التواصل:</strong> <span dir="ltr">{contact}</span></p>
            <p style="margin: 6px 0;"><strong>المدينة:</strong> {city}</p>
            <p style="margin: 6px 0;"><strong>اللغة / اللهجة:</strong> {dialect}</p>
            <p style="margin: 6px 0; color: #4338ca;"><strong>المنتجات محل الاهتمام:</strong> {products}</p>
            <p style="margin: 6px 0;"><strong>الهدف:</strong> {goal}</p>
            <p style="margin: 6px 0;"><strong>المستوى الحالي:</strong> {level}</p>
            <p style="margin: 6px 0; color: #b45309;"><strong>الاعتراضات:</strong> {objections}</p>
            <div style="background: #ffffff; padding: 10px; border-radius: 6px; margin-top: 10px; border-left: 4px solid #4338ca;">
                <strong>ملخّص المحادثة:</strong>
                <p style="margin: 4px 0; line-height: 1.5; color: #334155;">{summary}</p>
            </div>
            <p style="margin: 10px 0 0 0; color: #16a34a;"><strong>الإجراء التالي:</strong> {next_action}</p>
            <p style="margin: 8px 0 0 0; color: #94a3b8; font-size: 12px;" dir="ltr">التاريخ: {timestamp}</p>
        </div>
        """
        st.markdown(card_content, unsafe_allow_html=True)