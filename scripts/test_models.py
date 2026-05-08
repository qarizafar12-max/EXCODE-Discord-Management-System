"""Quick test to verify which Gemini models work with the current API key."""
from google import genai
from google.genai import types

API_KEY = "AIzaSyC88-8LoQtsgJ3nuYhV1zoL5p7QaGwocOg"
client = genai.Client(api_key=API_KEY)

MODELS_TO_TEST = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-pro-exp",
]

for model in MODELS_TO_TEST:
    try:
        resp = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=[types.Part(text="Say OK")])],
            config=types.GenerateContentConfig(max_output_tokens=10),
        )
        print(f"[OK]   {model} → {resp.text.strip()}")
    except Exception as e:
        err = str(e)[:120]
        if "429" in err or "EXHAUSTED" in err:
            print(f"[QUOTA] {model} → quota exhausted")
        elif "404" in err:
            print(f"[404]  {model} → model not found")
        else:
            print(f"[ERR]  {model} → {err}")
