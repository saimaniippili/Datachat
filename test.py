import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_experimental.agents import create_pandas_dataframe_agent

print("Initializing LLM...")
llm = ChatOpenAI(
    model='meta/llama-3.3-70b-instruct',
    temperature=0.2,
    base_url='https://integrate.api.nvidia.com/v1',
    api_key='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'
)
print("Creating agent...")
df = pd.DataFrame({'a': [1, 2, 3]})
agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True, agent_type="zero-shot-react-description")
print("Invoking...")
print(agent.invoke("What is the sum of column a?"))
print("Done!")
