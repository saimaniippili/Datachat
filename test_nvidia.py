from openai import OpenAI
client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)
try:
    completion = client.chat.completions.create(
      model="meta/llama-3.3-70b-instruct",
      messages=[{"role":"user","content":"Say hi"}],
      max_tokens=10,
      timeout=15.0
    )
    print("API SUCCESS:", completion.choices[0].message.content)
except Exception as e:
    print("API ERROR:", repr(e))
