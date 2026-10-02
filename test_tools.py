"""Run with python test_tools.py. No API key is needed."""

import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import agent
import tools


def model_reply(name=None, arguments=None, content=None, call_id="call_1"):
    calls = [] if name is None else [SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )]
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls)
    )])


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.original = copy.deepcopy(tools.AVAILABILITY)
        self.reservations = copy.deepcopy(tools.RESERVATIONS)

    def tearDown(self):
        tools.AVAILABILITY.clear()
        tools.AVAILABILITY.update(self.original)
        tools.RESERVATIONS[:] = self.reservations

    def test_reads_do_not_change_state(self):
        self.assertIn("214", tools.check_availability(" monday "))
        self.assertIn("8:00 AM", tools.get_hours("Friday"))
        self.assertEqual(tools.AVAILABILITY, self.original)
        self.assertEqual(tools.RESERVATIONS, self.reservations)

    def test_invalid_day_and_empty_day(self):
        self.assertIn("Invalid day", tools.check_availability("Sunday"))
        self.assertIn("Invalid day", tools.get_hours("Sunday"))
        self.assertIn("No study rooms", tools.check_availability("Thursday"))

    def test_booking_changes_state_and_rejects_duplicate(self):
        self.assertIn("Booked", tools.book_room("Monday", "214", "Bruce"))
        self.assertNotIn("214", tools.AVAILABILITY["Monday"])
        self.assertEqual(len(tools.RESERVATIONS), len(self.reservations) + 1)
        self.assertIn("not available", tools.book_room("Monday", "214", "Bruce"))
        self.assertEqual(len(tools.RESERVATIONS), len(self.reservations) + 1)

    def test_invalid_booking_leaves_state_unchanged(self):
        for args in [("Sunday", "214", "Bruce"), ("Monday", "999", "Bruce"),
                     ("Monday", "214", " "), ("Monday", 214, "Bruce")]:
            tools.book_room(*args)
        self.assertEqual(tools.AVAILABILITY, self.original)
        self.assertEqual(tools.RESERVATIONS, self.reservations)

    def test_unknown_tool_executes_nothing(self):
        spy = Mock()
        with patch.dict(tools.AVAILABLE_TOOLS, {"check_availability": spy}):
            result = agent.dispatch_tool("delete_all_reservations", "{}")
        self.assertIn("Unknown tool", result)
        spy.assert_not_called()
        self.assertEqual(tools.AVAILABILITY, self.original)

    def test_malformed_and_wrong_arguments(self):
        for raw in ['{"day":', '[]', '{"wrong": "Monday"}', '{"day": 1}']:
            with self.subTest(arguments=raw):
                self.assertIn("Tool failed", agent.dispatch_tool("get_hours", raw))

    def test_tool_exception_is_returned(self):
        with patch.dict(tools.AVAILABLE_TOOLS, {"get_hours": Mock(side_effect=RuntimeError("offline"))}):
            result = agent.dispatch_tool("get_hours", '{"day": "Monday"}')
        self.assertIn("offline", result)

    def test_dispatch_requires_confirmation(self):
        raw = json.dumps({"day": "Monday", "room": "214", "name": "Bruce"})
        self.assertIn("Confirmation required", agent.dispatch_tool("book_room", raw))
        self.assertEqual(tools.AVAILABILITY, self.original)
        # A model cannot add its own approval argument.
        injected = json.dumps({"day": "Monday", "room": "214", "name": "Bruce", "confirmed": True})
        self.assertIn("Tool failed", agent.dispatch_tool("book_room", injected))
        self.assertEqual(tools.AVAILABILITY, self.original)

    def test_loop_confirmation_and_cancellation(self):
        raw = json.dumps({"day": "Monday", "room": "214", "name": "Bruce"})
        for approved in [False, True]:
            client = Mock()
            client.chat.completions.create.side_effect = [
                model_reply("book_room", raw), model_reply(content="Finished")
            ]
            messages, log = [], []
            runner = agent.run_agent(client, messages, log)
            event = next(runner)
            self.assertEqual(event["type"], "confirmation")
            self.assertIn("214", event["content"])
            self.assertEqual(tools.AVAILABILITY, self.original)
            self.assertEqual(runner.send(approved)["type"], "answer")
            self.assertEqual("214" not in tools.AVAILABILITY["Monday"], approved)
            self.assertEqual(log[0]["result"], messages[1]["content"])

    def test_loop_multiple_rounds(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            model_reply("check_availability", '{"day": "Monday"}'),
            model_reply("get_hours", '{"day": "Monday"}', call_id="call_2"),
            model_reply(content="Rooms and hours checked."),
        ]
        messages, log = [], []
        self.assertEqual(next(agent.run_agent(client, messages, log))["type"], "answer")
        self.assertEqual(len(log), 2)
        self.assertEqual(client.chat.completions.create.call_count, 3)
        self.assertEqual([m["tool_call_id"] for m in messages if m["role"] == "tool"], ["call_1", "call_2"])

    def test_loop_returns_errors_to_model(self):
        client = Mock()
        client.chat.completions.create.side_effect = [
            model_reply("delete_all_reservations", "{}"),
            model_reply("get_hours", "{"),
            model_reply(content="Could not run those tools."),
        ]
        messages, log = [], []
        next(agent.run_agent(client, messages, log))
        self.assertIn("Unknown tool", messages[1]["content"])
        self.assertIn("Tool failed", messages[3]["content"])
        self.assertEqual(len(log), 2)

    def test_cap_stops_repeated_requests(self):
        client = Mock()
        client.chat.completions.create.return_value = model_reply("get_hours", '{"day": "Monday"}')
        messages, log = [], []
        event = next(agent.run_agent(client, messages, log))
        self.assertIn("limit", event["content"])
        self.assertEqual(client.chat.completions.create.call_count, 5)
        self.assertEqual(len(log), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
