"""CSC-128 Assignment 7: study-room agent interface.
Brayan Penaherrera
"""

import copy
import threading

import streamlit as st
from groq import Groq

import tools
from agent import run_agent

SYSTEM_PROMPT = """You are a helpful study-room assistant.
Use tools for availability, opening hours, and booking requests.
Ask for missing booking details: weekday, room number, and student name.
Never claim a booking succeeded unless the tool result says it succeeded.
When a student requests a booking and all three details are known, request
book_room now. Do not ask for confirmation in a chat message first.
The tool request opens the application's Confirm booking and Cancel booking
buttons. It does not create a reservation until the user clicks Confirm booking.
Never treat a chat reply as authorization to bypass those buttons.
After a cancellation, do not request that booking again unless the user asks anew.
Use the tool results as facts; do not invent availability or opening hours.
These are classroom example data, not a live campus booking system.
"""


@st.cache_resource
def shared_resources():
    """Keep the initial data and a lock shared across Streamlit sessions."""
    return threading.RLock(), copy.deepcopy(tools.AVAILABILITY)


def advance_agent(approval=None):
    """Run until the next UI event, with isolated data for this session."""
    lock, _ = shared_resources()
    # The course starter uses module-level data. Temporarily bind this
    # session's data while executing; restore the original objects afterward.
    # The lock prevents another browser session from seeing the swapped data.
    with lock:
        original_availability = tools.AVAILABILITY
        original_reservations = tools.RESERVATIONS
        tools.AVAILABILITY = st.session_state.availability
        tools.RESERVATIONS = st.session_state.reservations
        try:
            runner = st.session_state.runner
            if approval is None:
                event = next(runner)
            else:
                event = runner.send(approval)
        finally:
            tools.AVAILABILITY = original_availability
            tools.RESERVATIONS = original_reservations

    if event["type"] == "confirmation":
        st.session_state.pending = event
    else:
        st.session_state.chat.append(
            {"role": "assistant", "content": event["content"]})
        st.session_state.pending = None
        st.session_state.runner = None


st.set_page_config(page_title="Study Room Agent", page_icon="📚")
_, initial_availability = shared_resources()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.session_state.chat = []
    st.session_state.tool_log = []
    st.session_state.pending = None
    st.session_state.runner = None
    st.session_state.availability = copy.deepcopy(initial_availability)
    st.session_state.reservations = []

# Apply instruction updates to existing conversations on the next rerun.
st.session_state.messages[0] = {"role": "system", "content": SYSTEM_PROMPT}

st.title("Study Room Agent")
st.caption("Ask about available rooms or opening hours, then confirm a booking.")
st.info("Classroom demo: example data. Reservations are held in this browser session and are not saved to a database.")

try:
    api_key = st.secrets.get("GROQ_API_KEY", "")
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    api_key = ""

if not api_key or api_key == "YOUR_GROQ_API_KEY":
    st.warning('Add GROQ_API_KEY to .streamlit/secrets.toml to connect the model.')
    api_key = ""

for item in st.session_state.chat:
    with st.chat_message(item["role"]):
        st.write(item["content"])

if st.session_state.pending is not None:
    pending = st.session_state.pending
    st.warning("Confirm this action before any data changes:")
    st.write(pending["content"])
    confirm_column, cancel_column = st.columns(2)
    if confirm_column.button("Confirm booking", type="primary"):
        with st.spinner("Completing your request..."):
            advance_agent(True)
        st.rerun()
    if cancel_column.button("Cancel booking"):
        with st.spinner("Cancelling this booking request..."):
            advance_agent(False)
        st.rerun()

prompt = st.chat_input(
    "Example: Which rooms are available on Monday?",
    disabled=not api_key or st.session_state.pending is not None,
)
if prompt:
    item = {"role": "user", "content": prompt}
    st.session_state.chat.append(item)
    st.session_state.messages.append(dict(item))
    client = Groq(api_key=api_key)
    st.session_state.runner = run_agent(
        client, st.session_state.messages, st.session_state.tool_log
    )
    with st.spinner("Checking your request..."):
        advance_agent()
    st.rerun()

st.subheader("Tool call log")
if not st.session_state.tool_log:
    st.write("No tools have been requested yet.")
for number, entry in enumerate(st.session_state.tool_log, start=1):
    with st.expander(f"{number}. {entry['name']}", expanded=True):
        st.write("Call ID:", entry["tool_call_id"])
        st.write("Arguments:")
        st.code(entry["arguments"], language="json")
        st.write("Result:", entry["result"])

with st.expander("Reservations in this session"):
    if st.session_state.reservations:
        st.table(st.session_state.reservations)
    else:
        st.write("No reservations have been created.")
