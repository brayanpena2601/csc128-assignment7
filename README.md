# Assignment 7: Agent with tools

Student: Brayan Penaherrera

This classroom study-room assistant has three tools:

- `check_availability(day)` reads available rooms.
- `get_hours(day)` reads opening hours.
- `book_room(day, room, name)` creates a booking and removes the room from availability.

Availability and hours are example data. Each Streamlit session has its own
in-memory reservations. They are not saved to disk or shared as real campus
bookings. Each booking reserves a room for a weekday; there are no time slots.

## Run

Open a terminal in this folder. Activate your course virtual environment, then:

```powershell
python -m pip install -r requirements.txt
python test_tools.py
```

The tests need no API key. Before creating a secrets file, confirm that this
folder's `.gitignore` lists `.streamlit/secrets.toml`.

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. Replace
the placeholder with your Groq key locally. Never commit or share the key.
Inside your Git repository, verify:

```powershell
git check-ignore -v .streamlit/secrets.toml
```

Do not push if this prints nothing. Then start the app:

```powershell
python -m streamlit run app.py
```

The app uses `openai/gpt-oss-20b`, which supports local tool calling. The course model `llama-3.3-70b-versatile` returned HTTP 404 (`model_not_found`) for this account. The application passes the three
schemas and `tool_choice="auto"` on every model round.

## Safety and confirmation

The dispatcher checks tool names against `AVAILABLE_TOOLS` before looking up
any function. It parses JSON inside exception handling, checks required
parameter names and string values, and returns failures as tool results.
The agent stops after five model rounds with a clear message if unfinished.

For a booking, the agent pauses and displays the exact day, room and student
name. Only clicking **Confirm booking** resumes execution with approval.
Clicking **Cancel booking** returns a cancellation result without changing
data. The model cannot provide its own approval in its arguments. Each write
request, including multiple requests in one model response, requires its own
confirmation. Every request, raw arguments, and result appears in the tool log.

## A function deliberately not written

I did not write `delete_all_reservations`. It could erase other students'
bookings, destroy records, and make rooms appear free when they are reserved.
This assistant only needs to read information and create a requested booking.
A model instruction alone would not justify exposing a bulk-delete function.

## An unknown tool and the test that proves rejection

A request for `delete_all_reservations` returns an `Unknown tool` error as a
tool result. No function is executed. `test_unknown_tool_executes_nothing`
uses a mock function and proves it was never called and availability stayed
unchanged. `test_loop_returns_errors_to_model` also verifies that the error
is added to the conversation as a tool message.

## Description rewrite: incorrect tool selection

This was an additional controlled experiment with a deliberately ambiguous
draft of `check_availability`'s description. The draft was used in the experiment,
not previously deployed in the app. The actual API results are saved in
[`description_evidence.json`](description_evidence.json).

Question: `Are the study rooms open on Thursday?`

Before:

> Check whether study rooms are open on a given weekday. Use this when a student asks if rooms are open or available.

Observed call: `check_availability(day="Thursday")`.
The result was `No study rooms are available on Thursday.` The model then
incorrectly answered: "No, study rooms are not open on Thursday."

This was the wrong tool for an opening-hours question. An empty availability
list means every room is unavailable, not that the facility is closed.

After (the description now used in `tools.py`):

> Check which study rooms are free on a given weekday. Call this when a student asks which rooms are available or before proposing a room to book. Do not call this for opening hours or to determine whether the facility is open; use get_hours for those questions. An empty availability list means no rooms are free, not that the facility is closed. This only reads availability and does not reserve a room.

Observed call: `get_hours(day="Thursday")`.
The result was `Opening hours on Thursday: 8:00 AM to 8:00 PM.` The model
correctly answered that the study rooms were open during those hours.

Only the `check_availability` description changed between these two requests.
The model, system prompt, user question, other tool schemas, and
`tool_choice="auto"` stayed the same. Each request started with a fresh
conversation. No reservation was created or changed. This is evidence from
one saved before/after comparison, not a guarantee of identical model behavior
on every future request.

## Additional fix: booking confirmation timing

Prompt: `Book room 214 on Monday for Bruce.` This followed questions about
Monday availability and Friday hours.

Before:

> Request a study-room booking only when the student explicitly asks to reserve a room and supplies a weekday, room number, and their name. Ask for missing details first. Do not call this for questions about availability or hours. The application must obtain explicit user confirmation before executing this function; requesting it does not mean the booking is complete.

Observed behavior: the model asked for confirmation in chat instead of
requesting `book_room`. The log contained only `check_availability` and
`get_hours`, so the application could not display its confirmation buttons.
This was a delayed/missing tool request, not an unauthorized booking or a
different tool being executed.

After:

> Request a study-room booking only when the student explicitly asks to reserve a room and supplies a weekday, room number, and their name. Ask for missing details first. Once all details are known, request this tool immediately to display the app's Confirm booking and Cancel booking buttons. Do not ask for confirmation in chat before requesting this tool. The app pauses execution until the user clicks Confirm booking. Do not call this for availability or hours questions, or repeat a cancelled request unless the user asks to book again. A tool request alone does not mean a reservation has been created.

The system prompt was also clarified to leave confirmation to the application's
buttons. Both instructions changed, so this test does not isolate the effect
of the description alone. A live Groq test using the same three user requests
then produced a `book_room` request with Monday, 214, and Bruce. The agent
paused before changing state. Cancelling returned an answer and left the
availability and reservations unchanged. Separate UI tests verified both
buttons with simulated responses.

## Tests and remaining improvements

Run `python test_tools.py`. Tests cover reads, invalid days, bookings,
duplicates, invalid arguments, malformed JSON, unknown names, function
exceptions, confirmation/cancellation, multiple model rounds, and the cap.
Mock model responses exercise the loop without making API calls.

With more time, I would add persistent storage, authenticated users, real dates
and time slots, and a real availability source. Live Groq tests have verified availability, hours, and the booking confirmation pause and cancellation.

## Submit

Push this folder to a public GitHub repository without the secrets file or
virtual environment. Paste the repository link in Brightspace and also attach
`tools.py`, `agent.py`, `app.py`, and `test_tools.py`. Review this README before submitting.

