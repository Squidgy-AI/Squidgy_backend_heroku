from openai import OpenAI
# from openai.types import OpenAIError

# Replace with your actual API key

api_key1 = ""

client = OpenAI(api_key=api_key1)

try:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello, are you working?"}],
        max_tokens=10
    )
    print("✅ API key is valid. Response:")
    print(response.choices[0].message.content)

except Exception as e:
    print(f"❌ Unexpected error: {e}")
