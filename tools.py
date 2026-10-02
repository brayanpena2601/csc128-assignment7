"""CSC-128 Assignment 7: tools and their schemas.

Brayan Penaherrera
Availability and hours are example data, not live campus information.
State is kept in memory and resets when the Python process restarts.
"""

AVAILABILITY = {
    "Monday": ["214", "216", "220"],
    "Tuesday": ["214", "216"],
    "Wednesday": ["214", "216", "220"],
    "Thursday": [],
    "Friday": ["220"],
}

HOURS = {
    "Monday": "8:00 AM to 8:00 PM",
    "Tuesday": "8:00 AM to 8:00 PM",
    "Wednesday": "8:00 AM to 8:00 PM",
    "Thursday": "8:00 AM to 8:00 PM",
    "Friday": "8:00 AM to 5:00 PM",
}

# Records contain only bookings created in this running program.
RESERVATIONS = []


def normalize_day(day):
    """Validate a weekday and normalize capitalization/spaces."""
    if not isinstance(day, str):
        raise ValueError("Day must be a weekday name written as text.")
    normalized = day.strip().title()
    if normalized not in AVAILABILITY:
        raise ValueError("Invalid day. Choose Monday through Friday.")
    return normalized


def check_availability(day):
    """Return available rooms, distinguishing invalid days from empty days."""
    try:
        day = normalize_day(day)
    except ValueError as error:
        return str(error)
    rooms = AVAILABILITY[day]
    if not rooms:
        return f"No study rooms are available on {day}."
    return f"Available on {day}: " + ", ".join(rooms)


def get_hours(day):
    """Return opening hours for a valid weekday."""
    try:
        day = normalize_day(day)
    except ValueError as error:
        return str(error)
    return f"Opening hours on {day}: {HOURS[day]}."


def book_room(day, room, name):
    """Book one available room after the caller obtains user confirmation.

    The dispatcher must enforce confirmation before invoking this function.
    This function cannot cancel bookings or delete arbitrary records.
    """
    try:
        day = normalize_day(day)
    except ValueError as error:
        return str(error)
    if not isinstance(room, str) or not room.strip():
        return "Room must be a nonempty room number written as text."
    if not isinstance(name, str) or not name.strip():
        return "A nonempty student name is required."
    room = room.strip()
    name = name.strip()
    if room not in AVAILABILITY[day]:
        return f"Room {room} is not available on {day}. No booking was created."

    AVAILABILITY[day].remove(room)
    RESERVATIONS.append({"day": day, "room": room, "name": name})
    return f"Booked room {room} on {day} for {name}."


AVAILABLE_TOOLS = {
    "check_availability": check_availability,
    "get_hours": get_hours,
    "book_room": book_room,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Check available study rooms for a weekday. Call this when a "
                "student asks which rooms are free or before proposing a room "
                "to book. This only reads availability and does not reserve a room."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "Weekday name, Monday through Friday.",
                    },
                },
                "required": ["day"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hours",
            "description": (
                "Look up study-room opening hours. Call this when a student "
                "asks when the study rooms open or close on a weekday. "
                "Do not use this to check room availability or create bookings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "Weekday name, Monday through Friday.",
                    },
                },
                "required": ["day"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_room",
            "description": (
                "Request a study-room booking only when the student explicitly "
                "asks to reserve a room and supplies a weekday, room number, "
                "and their name. Ask for missing details first. Once all details "
                "are known, request this tool immediately to display the app's "
                "Confirm booking and Cancel booking buttons. Do not ask for "
                "confirmation in chat before requesting this tool. The app pauses "
                "execution until the user clicks Confirm booking. Do not call "
                "this for availability or hours questions, or repeat a cancelled "
                "request unless the user asks to book again. A tool request "
                "alone does not mean a reservation has been created."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "Weekday name, Monday through Friday.",
                    },
                    "room": {
                        "type": "string",
                        "description": "Available room number, for example 214.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the student requesting the booking.",
                    },
                },
                "required": ["day", "room", "name"],
                "additionalProperties": False,
            },
        },
    },
]

