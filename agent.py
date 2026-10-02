"""Safe tool dispatch and a resumable agent loop.

No API key or third-party imports are needed to test this module.
"""

import json

from tools import AVAILABLE_TOOLS, TOOL_SCHEMAS

MODEL = "openai/gpt-oss-20b"
MAX_ROUNDS = 5
WRITE_TOOLS = {"book_room"}


def parse_request(name, arguments):
    """Check the allowed name before lookup, then validate JSON arguments."""
    if name not in AVAILABLE_TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    args = json.loads(arguments)
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    schema = next(
        item["function"]["parameters"]
        for item in TOOL_SCHEMAS
        if item["function"]["name"] == name
    )
    if set(args) != set(schema["required"]):
        raise ValueError("Tool arguments must match the required parameter names.")
    if any(not isinstance(value, str) for value in args.values()):
        raise ValueError("Tool arguments must be strings.")
    return args


def dispatch_tool(name, arguments, *, confirmed=False):
    """Return failures as text; only trusted application code can confirm."""
    try:
        args = parse_request(name, arguments)
        if name in WRITE_TOOLS and confirmed is not True:
            return "Confirmation required. No booking was created."
        return str(AVAILABLE_TOOLS[name](**args))
    except Exception as error:
        return f"Tool failed: {error}"


def run_agent(client, messages, tool_log, max_rounds=MAX_ROUNDS):
    """Yield confirmation/answer events so a UI can pause without writing.

    Start with next(generator). For a confirmation event, display its exact
    details and call generator.send(True) only after a user confirms, or
    generator.send(False) after they cancel. The API cannot supply this value.
    """
    for _ in range(max_rounds):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
        except Exception as error:
            # Report safe diagnostics without exposing request headers or keys.
            status = getattr(error, "status_code", None)
            if status == 401:
                content = "Groq rejected the API key. Check your local secrets file and restart the app."
            elif status == 404:
                content = f"Groq could not find the configured model ({MODEL}) for this account."
            elif status == 429:
                content = "Groq's request limit was reached. Wait before trying again."
            elif status == 400:
                content = "Groq rejected the model request. The model may have generated an invalid tool call. Try rephrasing your request."
            else:
                content = "The model service could not complete the request. Check your connection and try again."
            yield {"type": "answer", "content": content}
            return

        message = response.choices[0].message
        if not message.tool_calls:
            content = message.content or "No response was returned."
            messages.append({"role": "assistant", "content": content})
            yield {"type": "answer", "content": content}
            return

        # Preserve the original tool requests before adding their results.
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in message.tool_calls
            ],
        })

        for call in message.tool_calls:
            name = call.function.name
            arguments = call.function.arguments
            entry = {
                "tool_call_id": call.id,
                "name": name,
                "arguments": arguments,
                "result": "Pending execution",
            }
            tool_log.append(entry)
            try:
                args = parse_request(name, arguments)
            except Exception as error:
                result = f"Tool failed: {error}"
            else:
                if name in WRITE_TOOLS:
                    entry["result"] = "Awaiting user confirmation; no data changed."
                    approved = yield {
                        "type": "confirmation",
                        "tool_call_id": call.id,
                        "name": name,
                        "arguments": dict(args),
                        "content": (
                            f"Book room {args['room']} on {args['day']} "
                            f"for {args['name']}?"
                        ),
                    }
                    if approved is True:
                        result = dispatch_tool(name, arguments, confirmed=True)
                    else:
                        result = "Booking cancelled by the user. No booking was created."
                else:
                    result = dispatch_tool(name, arguments)

            entry["result"] = result
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

    content = "I reached the tool-call round limit and could not finish this request. Please try a simpler request."
    messages.append({"role": "assistant", "content": content})
    yield {"type": "answer", "content": content}
