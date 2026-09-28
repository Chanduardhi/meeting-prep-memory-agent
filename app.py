import os
import sys
import csv
import pandas as pd
from datetime import datetime, date
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from hindsight_client import Hindsight

# Page Configuration
st.set_page_config(
    page_title="Contact Memory & Meeting Prep Agent",
    page_icon="📅",
    layout="wide"
)

# Load Environment Variables
load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY")
HINDSIGHT_KEY = os.getenv("HINDSIGHT_API_KEY")
BASE_URL = os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")

if not GROQ_KEY or not HINDSIGHT_KEY:
    st.error("Missing GROQ_API_KEY or HINDSIGHT_API_KEY in .env file.")
    st.stop()

# Initialize API Clients
groq_client = Groq(api_key=GROQ_KEY)
hindsight = Hindsight(base_url=BASE_URL, api_key=HINDSIGHT_KEY)

BANK_ID = "alex_nexuscorp_memory"
CSV_FILE = "client_meeting_tracker.csv"
REMINDERS_FILE = "client_reminders.csv"


# Ensure CSV Spreadsheets Exist
def init_storage():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=[
            "Timestamp", "Contact Name", "Company", "Role", "Meeting Notes / Debrief"
        ])
        df.to_csv(CSV_FILE, index=False)

    if not os.path.exists(REMINDERS_FILE):
        df = pd.DataFrame(columns=[
            "Contact Name", "Reminder Topic", "Due Date", "Status"
        ])
        df.to_csv(REMINDERS_FILE, index=False)


init_storage()


def retain_notes(contact_name: str, company: str, role: str, notes: str):
    """Store notes in Hindsight Cloud and local CSV spreadsheet."""
    formatted_content = f"Contact: {contact_name} ({role} at {company})\nNotes: {notes}"
    
    # 1. Hindsight Vector Retention
    hindsight.retain(bank_id=BANK_ID, content=formatted_content)
    
    # 2. Append to Spreadsheet
    new_row = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Contact Name": contact_name,
        "Company": company,
        "Role": role,
        "Meeting Notes / Debrief": notes
    }
    df = pd.read_csv(CSV_FILE)
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)


def generate_briefing(contact_name: str) -> str:
    """Recall client context from Hindsight and synthesize briefing via Groq."""
    query = f"Brief me on {contact_name} before our upcoming call."
    memories = hindsight.recall(bank_id=BANK_ID, query=query)
    
    context_text = "\n".join([f"- {m}" for m in memories]) if memories else "No context found."

    system_prompt = f"""You are an Executive Meeting Prep Assistant.
RECALLED CLIENT MEMORIES:
{context_text}

Format a concise pre-meeting briefing for {contact_name} including:
1. Communication Preferences
2. Promises / Commitments Made
3. Action Items & Key Discussion Topics
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
    )
    return response.choices[0].message.content


def save_reminder(contact_name: str, topic: str, due_date: date):
    """Save date reminder/alarm to CSV."""
    new_reminder = {
        "Contact Name": contact_name,
        "Reminder Topic": topic,
        "Due Date": due_date.strftime("%Y-%m-%d"),
        "Status": "Pending"
    }
    df = pd.read_csv(REMINDERS_FILE)
    df = pd.concat([df, pd.DataFrame([new_reminder])], ignore_index=True)
    df.to_csv(REMINDERS_FILE, index=False)


# UI Layout
st.title("💼 AI Meeting Prep & Contact Memory Agent")
st.markdown("Automated client contact tracking, Hindsight memory persistence, and executive briefings.")

# Sidebar Navigation
tab_option = st.sidebar.radio("Navigation", ["➕ Add New Person / Debrief", "👤 Contact Directory & Briefings", "⏰ Date Reminders & Alarms"])

df_contacts = pd.read_csv(CSV_FILE)

# ---------------------------------------------------------
# TAB 1: ADD NEW PERSON / DEBRIEF FORM
# ---------------------------------------------------------
if tab_option == "➕ Add New Person / Debrief":
    st.subheader("Add Contact Details & Meeting Debrief")
    
    with st.form("add_contact_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Person / Contact Name*", placeholder="e.g. Sarah Jenkins")
            company = st.text_input("Company Name", placeholder="e.g. NexusCorp")
        with col2:
            role = st.text_input("Role / Job Title", placeholder="e.g. CTO")
        
        notes = st.text_area("Meeting Debrief / Preferences / Promises*", placeholder="Paste raw notes, email text, or call summary...", height=150)
        
        submitted = st.form_submit_button("Save & Sync Memory Bank")
        
        if submitted:
            if name and notes:
                with st.spinner("Syncing to Hindsight Memory & Spreadsheet..."):
                    retain_notes(name, company, role, notes)
                st.success(f"Successfully saved details for **{name}**!")
            else:
                st.warning("Please fill in both Contact Name and Meeting Notes.")

    st.markdown("---")
    st.subheader("📊 Auto-Updated Spreadsheet Tracker")
    st.dataframe(df_contacts, use_container_width=True)

# ---------------------------------------------------------
# TAB 2: SPECIFIC PERSON BRIEFING & HISTORY
# ---------------------------------------------------------
elif tab_option == "👤 Contact Directory & Briefings":
    st.subheader("Specific Contact Selector & Executive Briefings")
    
    all_contacts = df_contacts["Contact Name"].dropna().unique().tolist()
    
    if not all_contacts:
        st.info("No contacts recorded yet. Add a person using the form first.")
    else:
        selected_contact = st.selectbox("Select a Person:", options=all_contacts)
        
        if selected_contact:
            col_a, col_b = st.columns([2, 1])
            
            with col_a:
                st.markdown(f"### Executive Briefing: **{selected_contact}**")
                if st.button("Generate Fresh AI Briefing"):
                    with st.spinner("Recalling from Hindsight & generating briefing..."):
                        briefing_text = generate_briefing(selected_contact)
                        st.markdown(briefing_text)
            
            with col_b:
                st.markdown("### Past Stored Logs")
                person_logs = df_contacts[df_contacts["Contact Name"] == selected_contact]
                for idx, row in person_logs.iterrows():
                    with st.expander(f"Log: {row['Timestamp']}"):
                        st.write(f"**Company:** {row['Company']}")
                        st.write(f"**Role:** {row['Role']}")
                        st.write(f"**Notes:** {row['Meeting Notes / Debrief']}")

# ---------------------------------------------------------
# TAB 3: DATE REMINDERS & ALARMS
# ---------------------------------------------------------
elif tab_option == "⏰ Date Reminders & Alarms":
    st.subheader("Set Date Reminders & Follow-up Alarms")
    
    all_contacts = df_contacts["Contact Name"].dropna().unique().tolist()
    
    if not all_contacts:
        st.info("Add a person first to set reminders.")
    else:
        with st.form("reminder_form", clear_on_submit=True):
            r_contact = st.selectbox("Select Person:", options=all_contacts)
            r_topic = st.text_input("Reminder Topic / Commitment", placeholder="e.g. Follow up on security audit zip link")
            r_date = st.date_input("Due Date / Reminder Date", value=date.today())
            
            r_submit = st.form_submit_button("Set Reminder Alarm")
            if r_submit:
                if r_topic:
                    save_reminder(r_contact, r_topic, r_date)
                    st.success(f"Reminder set for **{r_contact}** on **{r_date}**!")
                else:
                    st.warning("Please enter a reminder topic.")

    st.markdown("---")
    st.subheader("⏰ Active Reminders List")
    df_reminders = pd.read_csv(REMINDERS_FILE)
    st.dataframe(df_reminders, use_container_width=True)
