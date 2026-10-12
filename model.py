"""Model backends: the real Gemini Flash Lite client and a scripted mock."""

from __future__ import annotations

from google import genai
from google.genai import types


class GeminiModel:
    """Thin wrapper around the google-genai SDK for multimodal chat."""

    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, messages: list[dict], system_instruction: str) -> str:
        """Send the full conversation and return the model's text reply.

        ``messages`` is a list of dicts:
            {"role": "user", "image": <png bytes>, "text": "..."}
            {"role": "model", "text": "..."}
        """
        contents: list[types.Content] = []
        for message in messages:
            parts: list[types.Part] = []
            if message.get("image"):
                parts.append(types.Part.from_bytes(data=message["image"], mime_type="image/png"))
            parts.append(types.Part(text=message["text"]))
            contents.append(types.Content(role=message["role"], parts=parts))

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,
            ),
        )
        return response.text or ""


class MockModel:
    """Scripted stand-in so the whole loop can run without an API key.

    It plays a short, fixed sequence of actions and then finishes. Useful for
    exercising the screenshot -> model -> action -> repeat plumbing in --demo.
    """

    def __init__(self):
        self.calls = 0
        self.model = "mock (scripted demo)"

    def generate(self, messages: list[dict], system_instruction: str) -> str:
        self.calls += 1
        script = [
            '{"action": "move", "x": 500, "y": 500}',
            '{"action": "click", "x": 500, "y": 500}',
            '{"action": "type", "text": "Hello from osctrl demo"}',
            '{"action": "press", "key": "enter"}',
            '{"action": "done", "message": "Demo finished"}',
        ]
        return script[min(self.calls - 1, len(script) - 1)]
