import html
import os
import re
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv


# Load the project-root environment file.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from api_client import ChatbotAPIError, chat_completion


st.set_page_config(
    page_title="School AI Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# All styling is included here, so no separate styles.css is required.
st.markdown(
    r"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        --school-navy: #0f1e36;
        --school-navy-2: #1b3a6b;
        --school-blue: #2563eb;
        --school-blue-dark: #1d4ed8;
        --school-blue-soft: #e0ebff;
        --school-sidebar: #f1f5fb;
        --school-bg: #f5f8fd;
        --school-border: #dbe5f1;
        --school-text: #1e293b;
        --school-muted: #64748b;
        --school-radius: 14px;
        --school-shadow-sm: 0 1px 2px rgba(15, 23, 42, .04), 0 1px 3px rgba(15, 23, 42, .04);
        --school-shadow-md: 0 8px 24px rgba(30, 64, 120, .10);
    }

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background:
            radial-gradient(900px 420px at 85% -10%, rgba(37,99,235,.08), transparent 60%),
            radial-gradient(700px 380px at 10% 110%, rgba(99,102,241,.06), transparent 60%),
            var(--school-bg) !important;
        color: var(--school-text);
        font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {
        visibility: hidden !important;
        height: 0 !important;
    }

    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stMain"] {
        padding-top: 0 !important;
    }

    .block-container {
        max-width: 1400px !important;
        padding-top: 6.2rem !important;
        padding-bottom: 1.6rem !important;
    }

    div[data-testid="stAlert"] {
        margin-top: 2px;
    }

    /* Hide welcome cards while the assistant is processing. */
    .stApp[data-test-script-state="running"] [data-testid="stHorizontalBlock"]:has(.feature-card),
    .stApp[data-test-script-state="running"] [data-testid="stElementContainer"]:has(.welcome-area),
    [data-stale="true"]:has(.feature-card),
    [data-stale="true"]:has(.welcome-area) {
        display: none !important;
    }

    /* ---------- Top application header ---------- */
    .school-topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 72px;
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 0 26px;
        box-sizing: border-box;
        color: #fff;
        background: linear-gradient(120deg, var(--school-navy) 0%, #15294a 55%, var(--school-navy-2) 100%);
        border-bottom: 1px solid rgba(255,255,255,.08);
        box-shadow: 0 4px 18px rgba(15, 23, 42, .18);
    }

    .school-brand {
        display: flex;
        align-items: center;
        gap: 13px;
        min-width: 0;
    }

    .school-brand-icon {
        width: 44px;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        background: linear-gradient(145deg, rgba(255,255,255,.22), rgba(255,255,255,.08));
        border: 1px solid rgba(255,255,255,.18);
        box-shadow: inset 0 1px 0 rgba(255,255,255,.15);
        font-size: 24px;
        flex: 0 0 auto;
    }

    .school-brand-title {
        margin: 0;
        font-size: 19px;
        line-height: 1.25;
        font-weight: 750;
        letter-spacing: -.2px;
        color: #fff;
    }

    .school-brand-subtitle {
        margin-top: 3px;
        color: #b9c7dc;
        font-size: 12px;
        line-height: 1.3;
    }

    .school-status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 6px 13px;
        font-size: 12px;
        font-weight: 700;
        white-space: nowrap;
        border: 1px solid transparent;
    }

    .school-status.online {
        color: #86efac;
        background: rgba(34,197,94,.14);
        border-color: rgba(34,197,94,.30);
    }

    .school-status.offline {
        color: #fcd34d;
        background: rgba(245,158,11,.14);
        border-color: rgba(245,158,11,.30);
    }

    .school-status-dot {
        width: 8px;
        height: 8px;
        display: inline-block;
        border-radius: 50%;
    }

    .school-status.online .school-status-dot {
        background: #22c55e;
        box-shadow: 0 0 0 0 rgba(34,197,94,.6);
        animation: school-pulse 2s infinite;
    }

    .school-status.offline .school-status-dot {
        background: #f59e0b;
    }

    @keyframes school-pulse {
        0%   { box-shadow: 0 0 0 0 rgba(34,197,94,.55); }
        70%  { box-shadow: 0 0 0 7px rgba(34,197,94,0); }
        100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
    }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        top: 72px !important;
        height: calc(100vh - 72px) !important;
        min-width: 315px !important;
        max-width: 315px !important;
        background: var(--school-sidebar) !important;
        border-right: 1px solid var(--school-border);
    }

    section[data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #f4f8fd 0%, #eaf1f9 100%) !important;
        padding: 18px 14px 16px 14px !important;
    }

    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {
        color: #5b6b82 !important;
        font-size: 11.5px !important;
        font-weight: 750 !important;
        text-transform: uppercase;
        letter-spacing: .9px;
        margin-top: 14px !important;
        margin-bottom: 8px !important;
        padding: 0 !important;
    }

    section[data-testid="stSidebar"] [data-testid="stButton"] button,
    section[data-testid="stSidebar"] [data-testid="stPopover"] > button {
        width: 100%;
        min-height: 47px;
        border-radius: 11px;
        border: 1px solid #d6e0ec;
        background: #fff;
        color: #243247;
        text-align: left;
        font-size: 14px;
        font-weight: 550;
        box-shadow: var(--school-shadow-sm);
        transition: all .18s ease;
    }

    section[data-testid="stSidebar"] [data-testid="stButton"] button:hover:not(:disabled),
    section[data-testid="stSidebar"] [data-testid="stPopover"] > button:hover {
        border-color: #93b4f8;
        background: #f7faff;
        color: var(--school-blue-dark);
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(37,99,235,.10);
    }

    section[data-testid="stSidebar"] [data-testid="stButton"] button:disabled {
        opacity: .55;
        background: #f6f8fb;
        cursor: not-allowed;
    }

    section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"],
    section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #2f6df0 0%, #1d4ed8 100%);
        border: none;
        color: #fff;
        font-weight: 650;
        text-align: center;
        box-shadow: 0 6px 16px rgba(37,99,235,.28);
    }

    section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]:hover,
    section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:hover {
        background: linear-gradient(135deg, #3b7bff 0%, #1e55e6 100%);
        color: #fff;
        box-shadow: 0 8px 20px rgba(37,99,235,.36);
    }

    section[data-testid="stSidebar"] [data-testid="stTextInput"] label p {
        font-size: 12.5px;
        font-weight: 600;
        color: #3b4a60;
    }

    section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
        min-height: 43px;
        border-radius: 10px;
        border: 1px solid #cdd9e7;
        background: #fff;
        font-size: 14px;
        transition: border-color .15s ease, box-shadow .15s ease;
    }

    section[data-testid="stSidebar"] [data-testid="stTextInput"] input:focus {
        border-color: #7aa3f7;
        box-shadow: 0 0 0 3px rgba(37,99,235,.12);
    }

    section[data-testid="stSidebar"] [data-testid="stForm"] {
        padding: 14px;
        border: 1px solid #d6e0ec;
        border-radius: 14px;
        background: rgba(255,255,255,.85);
        box-shadow: var(--school-shadow-sm);
    }

    .sidebar-separator {
        height: 1px;
        background: linear-gradient(90deg, transparent, #c3d1e2 20%, #c3d1e2 80%, transparent);
        margin: 18px 0 16px;
        width: 100%;
    }

    .sidebar-spacer {
        height: clamp(20px, calc(100vh - 650px), 310px);
        min-height: 20px;
    }

    .profile-summary {
        display: flex;
        align-items: center;
        gap: 11px;
        margin: 0 0 9px;
        padding: 11px 12px;
        border: 1px solid #d6e0ec;
        border-radius: 13px;
        background: #fff;
        box-shadow: var(--school-shadow-sm);
    }

    .profile-avatar {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        color: #fff;
        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        font-size: 20px;
        flex: 0 0 auto;
        box-shadow: 0 4px 10px rgba(37,99,235,.30);
    }

    .profile-name {
        color: #172033;
        font-size: 13.5px;
        font-weight: 700;
        line-height: 1.4;
        overflow-wrap: anywhere;
    }

    .profile-role {
        display: inline-block;
        margin-top: 3px;
        padding: 1px 9px;
        border-radius: 999px;
        color: var(--school-blue-dark);
        background: var(--school-blue-soft);
        font-size: 11px;
        font-weight: 650;
    }

    /* ---------- Main workspace ---------- */
    .welcome-area {
        text-align: center;
        padding: 34px 16px 20px;
        margin: 2px auto 22px;
        max-width: 780px;
    }

    .welcome-icon {
        width: 64px;
        height: 64px;
        margin: 0 auto 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 18px;
        background: linear-gradient(145deg, #e8f0ff, #d3e2ff);
        color: var(--school-blue);
        font-size: 28px;
        box-shadow: 0 10px 24px rgba(37,99,235,.16);
    }

    .welcome-title {
        font-size: 26px;
        font-weight: 800;
        line-height: 1.3;
        margin: 0 0 8px;
        letter-spacing: -.4px;
        background: linear-gradient(90deg, #14243b, #2563eb);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: #172033;
    }

    .welcome-copy {
        color: var(--school-muted);
        font-size: 14px;
        line-height: 1.7;
        margin: 0;
    }

    .feature-card {
        min-height: 118px;
        padding: 19px 19px 16px;
        border: 1px solid var(--school-border);
        border-radius: var(--school-radius);
        background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
        box-shadow: var(--school-shadow-sm);
        transition: all .2s ease;
        position: relative;
        overflow: hidden;
    }

    .feature-card::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
        background: linear-gradient(180deg, #3b82f6, #6366f1);
        opacity: .85;
    }

    .feature-card:hover {
        transform: translateY(-3px);
        border-color: #b7cdf7;
        box-shadow: var(--school-shadow-md);
    }

    .feature-title {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #1e3a5f;
        font-size: 15px;
        font-weight: 750;
        margin-bottom: 9px;
    }

    .feature-title span {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 9px;
        background: var(--school-blue-soft);
        font-size: 16px;
    }

    .feature-copy {
        color: #64748b;
        font-size: 12.5px;
        line-height: 1.6;
    }

    /* Buttons in the main area. */
    [data-testid="stMain"] [data-testid="stButton"] button,
    [data-testid="stAppViewContainer"] .main [data-testid="stButton"] button {
        border-radius: 10px;
        border: 1px solid #c9d9f3;
        background: #fff;
        color: var(--school-blue-dark);
        font-size: 13px;
        font-weight: 600;
        min-height: 40px;
        transition: all .18s ease;
    }

    [data-testid="stMain"] [data-testid="stButton"] button:hover,
    [data-testid="stAppViewContainer"] .main [data-testid="stButton"] button:hover {
        background: var(--school-blue);
        border-color: var(--school-blue);
        color: #fff;
        box-shadow: 0 6px 16px rgba(37,99,235,.25);
    }

    /* Chat messages */
    [data-testid="stChatMessage"] {
        border: 1px solid var(--school-border);
        border-radius: var(--school-radius);
        background: #fff;
        padding: 15px 18px;
        margin-bottom: 14px;
        box-shadow: var(--school-shadow-sm);
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #eaf2ff 0%, #f3f7ff 100%);
        border-color: #c9dcfb;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        border-left: 4px solid var(--school-blue);
    }

    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li {
        color: #253247;
        font-size: 14.5px;
        line-height: 1.7;
    }

    [data-testid="stChatMessage"] table {
        border-collapse: collapse;
        border-radius: 8px;
        overflow: hidden;
    }

    [data-testid="stChatMessage"] th {
        background: #eef4fd;
    }

    /* Chat input */
    [data-testid="stChatInput"] {
        padding-top: 8px;
        background: transparent;
    }

    [data-testid="stChatInput"] > div {
        border-radius: 14px !important;
        border: 1px solid #c6d6ea !important;
        background: #fff !important;
        box-shadow: 0 6px 20px rgba(30,64,120,.08) !important;
    }

    [data-testid="stChatInput"] textarea {
        min-height: 56px !important;
        border-radius: 14px !important;
        background: transparent !important;
        box-shadow: none !important;
        font-size: 14.5px !important;
    }

    [data-testid="stChatInput"]:focus-within > div {
        border-color: #7aa3f7 !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,.12), 0 6px 20px rgba(30,64,120,.10) !important;
    }

    [data-testid="stChatInput"] button {
        background: var(--school-blue) !important;
        color: #fff !important;
        border-radius: 10px !important;
    }

    .footer-note {
        text-align: center;
        color: #8190a5;
        font-size: 11.5px;
        padding: 10px 0 0;
    }

    div[data-testid="stAlert"] {
        border-radius: 11px;
        border: 1px solid rgba(0,0,0,.04);
    }

    /* Slim scrollbars */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: #c5d2e3; border-radius: 8px; }
    ::-webkit-scrollbar-thumb:hover { background: #a9bbd2; }

    @media (max-width: 800px) {
        .school-topbar { height: 66px; padding: 0 12px; }
        .school-brand-title { font-size: 16px; }
        .school-brand-subtitle { font-size: 11px; }
        .school-brand-icon { width: 38px; height: 38px; }

        [data-testid="stAppViewContainer"] > .main,
        [data-testid="stMain"] {
            padding-top: 0 !important;
        }

        section[data-testid="stSidebar"] {
            top: 66px !important;
            height: calc(100vh - 66px) !important;
            min-width: min(84vw, 315px) !important;
            max-width: min(84vw, 315px) !important;
        }

        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 5.6rem !important;
        }

        .welcome-area { padding-top: 18px; }
        .welcome-title { font-size: 22px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Session state
# ---------------------------------------------------------

DEFAULT_STATE = {
    "messages": [],
    "ui_user_id": uuid.uuid4().hex,
    "ui_chat_id": uuid.uuid4().hex,
    "pending_prompt": None,
    "is_authenticated": False,
    "profile": {},
    "login_error_field": None,
    "login_error_message": "",
    "login_success_notice": False,
    "logout_notice": None,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# Clear the password widget state after each login attempt.
if st.session_state.pop("clear_password_next_run", False):
    st.session_state["login_password"] = ""


def ask_chatbot(messages: list[dict[str, str]]) -> str:
    """Send messages to the existing FastAPI chatbot."""
    return chat_completion(
        messages=messages,
        ui_user_id=st.session_state.ui_user_id,
        ui_chat_id=st.session_state.ui_chat_id,
    )


def classify_login_reply(reply: str) -> str:
    """Classify the text response for UI display only."""
    text = reply.casefold()

    failure_markers = (
        "login failed",
        "invalid email or password",
        "failed to log in",
        "invalid credentials",
        "authentication failed",
        "too many failed attempts",
        "too many login attempts",
        "locked out",
        "no role that can use this assistant",
    )

    if any(marker in text for marker in failure_markers):
        return "error"

    success_markers = (
        "login successful",
        "logged in as",
        "successfully logged in",
        "you are now logged in",
    )

    if any(marker in text for marker in success_markers):
        return "success"

    return "info"


def split_permission_list(value: str) -> list[str]:
    value = value.strip().rstrip(".")

    if not value or value.casefold() in {"none", "n/a", "not provided"}:
        return []

    return [item.strip() for item in value.split(",") if item.strip()]


def parse_login_profile(reply: str) -> dict[str, Any] | None:
    """Parse profile details from the current plain-text login response."""
    welcome_match = re.search(
        r"Welcome,\s*(?P<name>.+?)!\s*You are logged in as\s+"
        r"\*{0,2}(?P<role>[^*\n.]+)\*{0,2}\.?",
        reply,
        re.IGNORECASE,
    )

    detail_match = re.search(
        r"Logged-in user:\s*(?P<name>.*?)\s*"
        r"\(role:\s*(?P<role>[^)]+)\)",
        reply,
        re.IGNORECASE,
    )

    name = ""
    role = ""

    if welcome_match:
        name = welcome_match.group("name").strip()
        role = welcome_match.group("role").strip()
    elif detail_match:
        name = detail_match.group("name").strip()
        role = detail_match.group("role").strip()

    details_match = re.search(
        r"Scope:\s*(?P<scope>.*?)\s*"
        r"Allowed information:\s*(?P<allowed>.*?)\s*"
        r"NOT allowed for this role:\s*(?P<denied>.*?)\s*"
        r"Active student_id:\s*(?P<student>[^\r\n]*)",
        reply,
        re.IGNORECASE | re.DOTALL,
    )

    scope = "Not provided"
    allowed: list[str] = []
    denied: list[str] = []
    active_student_id = None

    if details_match:
        scope = details_match.group("scope").strip().rstrip(".")
        allowed = split_permission_list(details_match.group("allowed"))
        denied = split_permission_list(details_match.group("denied"))

        student = details_match.group("student").strip().rstrip(".")

        if student and student.casefold() != "none":
            active_student_id = student

    if not name and not role:
        return None

    return {
        "name": name or "Name not provided",
        "role": role or "Role not provided",
        "scope": scope,
        "allowed_information": allowed,
        "restricted_information": denied,
        "active_student_id": active_student_id,
    }


def login_error_for_reply(reply: str) -> tuple[str, str]:
    text = reply.casefold()

    if "too many failed attempts" in text or "too many login attempts" in text:
        return "form", "Too many failed attempts. Please try again later."

    if "no role that can use this assistant" in text:
        return "form", "Your account does not have a role that can use this assistant."

    if any(
        marker in text
        for marker in (
            "login failed",
            "invalid email or password",
            "invalid credentials",
            "authentication failed",
        )
    ):
        return "password", "Invalid school email or password. Please check your credentials."

    return "form", "We could not confirm your login. Please try again."


def reset_login_errors() -> None:
    st.session_state.login_error_field = None
    st.session_state.login_error_message = ""


def queue_prompt(prompt: str) -> None:
    st.session_state.pending_prompt = prompt
    st.rerun()


if not os.getenv("CHATBOT_API_KEY", "").strip():
    st.error(
        "CHATBOT_API_KEY is missing. Check the existing .env file in the project root."
    )
    st.stop()


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

status_text = "Connected" if st.session_state.is_authenticated else "Sign in required"
status_class = "online" if st.session_state.is_authenticated else "offline"

st.markdown(
    f"""
    <div class="school-topbar">
        <div class="school-brand">
            <div class="school-brand-icon">🎓</div>
            <div>
                <div class="school-brand-title">School AI Assistant</div>
                <div class="school-brand-subtitle">Your intelligent school management companion</div>
            </div>
        </div>
        <div class="school-status {status_class}">
            <span class="school-status-dot"></span>{status_text}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

with st.sidebar:
    if st.button("＋  New Chat", use_container_width=True, key="new_chat"):
        st.session_state.messages = []
        st.session_state.pending_prompt = None

        # Keep the current chat ID so the backend's owner:chat session remains authenticated.
        # A new chat ID would make the backend look for a different, unauthenticated session.
        st.rerun()

    st.markdown("### Quick Actions")

    quick_prompts = [
        ("📖", "My Subjects", "What subjects do I study in my class?"),
        ("▦", "My Timetable", "What is my timetable?"),
        ("▣", "Attendance", "Show my attendance summary."),
    ]

    for index, (icon, label, prompt_text) in enumerate(quick_prompts):
        if st.button(
            f"{icon}  {label}",
            key=f"quick_prompt_{index}",
            use_container_width=True,
            disabled=not st.session_state.is_authenticated,
        ):
            queue_prompt(prompt_text)

    if not st.session_state.is_authenticated:
        st.markdown(
            '<div class="sidebar-separator"></div>',
            unsafe_allow_html=True,
        )
        st.markdown("### Sign In")

        if st.session_state.logout_notice:
            st.info(st.session_state.logout_notice)
            st.session_state.logout_notice = None

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "School Email",
                placeholder="you@school.com",
                key="login_email",
            )

            if st.session_state.login_error_field == "email":
                st.error(st.session_state.login_error_message)

            password = st.text_input(
                "Password",
                type="password",
                key="login_password",
            )

            if st.session_state.login_error_field == "password":
                st.error(st.session_state.login_error_message)

            login_submitted = st.form_submit_button(
                "Sign In to School AI",
                type="primary",
                use_container_width=True,
            )

        if st.session_state.login_error_field == "form":
            st.error(st.session_state.login_error_message)

        if login_submitted:
            reset_login_errors()
            st.session_state.clear_password_next_run = True

            if not email.strip():
                st.session_state.login_error_field = "email"
                st.session_state.login_error_message = (
                    "Please enter your school email."
                )

            elif not password:
                st.session_state.login_error_field = "password"
                st.session_state.login_error_message = (
                    "Please enter your password."
                )

            else:
                login_message = {
                    "role": "user",
                    "content": f"/login {email.strip()} {password}",
                }

                try:
                    with st.spinner("Connecting to your school account..."):
                        reply = ask_chatbot([login_message])

                    status = classify_login_reply(reply)

                    if status == "success":
                        profile = parse_login_profile(reply)

                        if profile is None:
                            try:
                                ask_chatbot(
                                    [{"role": "user", "content": "/logout"}]
                                )
                            except ChatbotAPIError:
                                pass

                            st.session_state.login_error_field = "form"
                            st.session_state.login_error_message = (
                                "The login response could not be read. Please try again."
                            )

                        else:
                            st.session_state.is_authenticated = True
                            st.session_state.profile = profile
                            st.session_state.login_success_notice = True
                            st.session_state.messages = []
                            st.session_state.pending_prompt = None
                            reset_login_errors()

                    elif status == "error":
                        field, message = login_error_for_reply(reply)
                        st.session_state.login_error_field = field
                        st.session_state.login_error_message = message

                    else:
                        st.session_state.login_error_field = "form"
                        st.session_state.login_error_message = (
                            "We could not verify the login. Please check your credentials and try again."
                        )

                except ChatbotAPIError:
                    st.session_state.login_error_field = "form"
                    st.session_state.login_error_message = (
                        "Could not connect to the chatbot service. Please try again."
                    )

            st.rerun()

    else:
        # Keep the profile card near the bottom of the sidebar.
        st.markdown(
            '<div class="sidebar-spacer"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sidebar-separator"></div>',
            unsafe_allow_html=True,
        )

        profile = st.session_state.profile
        role_label = str(profile.get("role", "User")).strip().title()
        name = str(profile.get("name", "User Profile")).strip()

        safe_name = html.escape(name)
        safe_role_label = html.escape(role_label)

        st.markdown(
            f"""
            <div class="profile-summary">
                <div class="profile-avatar">♙</div>
                <div>
                    <div class="profile-name">{safe_name}</div>
                    <div class="profile-role">{safe_role_label}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.popover("View profile and log out", use_container_width=True):
            st.markdown("### User Profile")
            st.write(f"**{name}**")
            st.caption(f"Role: {profile.get('role', 'Not provided')}")

            with st.expander("Access scope"):
                st.write(profile.get("scope", "Not provided"))

            with st.expander("Access permissions"):
                allowed = profile.get("allowed_information", [])
                restricted = profile.get("restricted_information", [])

                st.caption("Allowed information")
                st.write(", ".join(allowed) if allowed else "Not listed")

                st.caption("Restricted information")
                st.write(", ".join(restricted) if restricted else "None listed")

                if profile.get("active_student_id"):
                    st.caption("Active student ID")
                    st.write(profile["active_student_id"])

            if st.button(
                "Log Out",
                key="profile_logout_button",
                use_container_width=True,
            ):
                logout_error = False

                try:
                    with st.spinner("Signing out..."):
                        ask_chatbot(
                            [{"role": "user", "content": "/logout"}]
                        )
                except ChatbotAPIError:
                    logout_error = True

                st.session_state.is_authenticated = False
                st.session_state.profile = {}
                st.session_state.messages = []
                st.session_state.pending_prompt = None
                st.session_state.login_success_notice = False

                # Generate a fresh chat ID after logout.
                st.session_state.ui_chat_id = uuid.uuid4().hex

                reset_login_errors()

                st.session_state.logout_notice = (
                    "You have been signed out on this screen. The server could not confirm logout."
                    if logout_error
                    else "You have been logged out."
                )

                st.rerun()


# ---------------------------------------------------------
# Main chat workspace
# ---------------------------------------------------------

if st.session_state.login_success_notice:
    st.success("Login successful!")
    st.session_state.login_success_notice = False


if not st.session_state.is_authenticated:
    st.markdown(
        """
        <div class="welcome-area">
            <div class="welcome-icon">✧</div>
            <div class="welcome-title">How can I help you?</div>
            <p class="welcome-copy">
                Sign in to ask about your school, classes, timetable, and academic records.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="welcome-area">
                <div class="welcome-icon">✧</div>
                <div class="welcome-title">How can I help you?</div>
                <p class="welcome-copy">
                    Ask about your school, classes, timetable, attendance, or academic records.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        feature_columns = st.columns(3, gap="medium")

        feature_cards = [
            (
                "📖",
                "My Subjects",
                "Find subjects assigned to your class.",
                "What subjects do I study in my class?",
            ),
            (
                "▦",
                "My Timetable",
                "Check your available timetable details.",
                "What is my timetable?",
            ),
            (
                "▣",
                "My Attendance",
                "Request your attendance summary.",
                "Show my attendance summary.",
            ),
        ]

        for index, column in enumerate(feature_columns):
            icon, title, description, prompt_text = feature_cards[index]

            with column:
                st.markdown(
                    f"""
                    <div class="feature-card">
                        <div class="feature-title">
                            <span>{icon}</span>{title}
                        </div>
                        <div class="feature-copy">{description}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    f"Ask about {title}",
                    key=f"feature_prompt_{index}",
                    use_container_width=True,
                ):
                    queue_prompt(prompt_text)

    for message in st.session_state.messages:
        avatar = "🎓" if message["role"] == "assistant" else "🙂"

        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])


prompt = st.chat_input(
    "Ask your school assistant...",
    disabled=not st.session_state.is_authenticated,
)

if not prompt and st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None


if prompt and prompt.strip() and st.session_state.is_authenticated:
    prompt = prompt.strip()

    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    try:
        with st.spinner("Checking school information..."):
            answer = ask_chatbot(st.session_state.messages)

        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )

        st.rerun()

    except ChatbotAPIError:
        if (
            st.session_state.messages
            and st.session_state.messages[-1].get("role") == "user"
        ):
            st.session_state.messages.pop()

        st.error(
            "Could not retrieve school information. Please try again."
        )


st.markdown(
    '<div class="footer-note">AI responses may need verification against official school records.</div>',
    unsafe_allow_html=True,
)