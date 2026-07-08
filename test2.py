import pandas as pd
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_experimental.agents import create_pandas_dataframe_agent

print("Initializing LLM...")
llm = ChatNVIDIA(
    model='meta/llama-3.3-70b-instruct',
    temperature=0.2,
    api_key='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',
    timeout=120
)
print("Creating agent...")
df = pd.DataFrame({'a': [1, 2, 3]})
agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True, agent_type="tool-calling")
print("Invoking...")
try:
    print(agent.invoke("What is the sum of column a?"))
except Exception as e:
    print("ERROR:", e)
print("Done!")
