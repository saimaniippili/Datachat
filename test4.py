import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_experimental.agents import create_pandas_dataframe_agent

print("Initializing LLM...")
llm = ChatOpenAI(
    model='nvidia/nemotron-3-ultra-550b-a55b',
    temperature=1,
    base_url='https://integrate.api.nvidia.com/v1',
    api_key='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',
    model_kwargs={"extra_body": {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}}
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
