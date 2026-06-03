import os
import io
import json
import sqlite3
import shutil
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_ollama import ChatOllama
from datetime import datetime

import sys

app = FastAPI(title="DataChat API")

# Setup directories for static files and templates
if getattr(sys, 'frozen', False):
    # If bundled as executable, read-only assets are extracted to MEIPASS
    ASSETS_DIR = sys._MEIPASS
    # Writable data (DB, charts, uploads) goes next to the .exe
    PERSISTENT_DIR = os.path.dirname(sys.executable)
else:
    # If running as script
    ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
    PERSISTENT_DIR = ASSETS_DIR

STATIC_DIR = os.path.join(ASSETS_DIR, "static")
TEMPLATES_DIR = os.path.join(ASSETS_DIR, "templates")

CHARTS_DIR = os.path.join(PERSISTENT_DIR, "charts")
DATA_DIR = os.path.join(PERSISTENT_DIR, "data")
DB_PATH = os.path.join(PERSISTENT_DIR, "datachat.db")

# Create directories if they don't exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Mount separate static and charts directories so charts can persist outside MEIPASS
app.mount("/static/charts", StaticFiles(directory=CHARTS_DIR), name="charts")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Database initialization
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filepath TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/models")
def get_models():
    """Fetch available models from the local Ollama instance."""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        data = response.json()
        models = [model["name"] for model in data.get("models", [])]
        return {"models": models}
    except Exception as e:
        # Fallback if Ollama is unreachable
        return {"models": ["llama3:8b", "mistral:latest", "gemma2:2b"]}

@app.get("/api/sessions")
def get_sessions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    sessions = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"sessions": sessions}

@app.get("/api/sessions/{session_id}")
def get_session(session_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    session = c.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    
    c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    messages = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    # Calculate profile quickly
    try:
        filepath = session["filepath"]
        if filepath.endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
            
        profile = {
            "rows": len(df),
            "cols": len(df.columns),
            "columns": [{"name": col, "type": str(df[col].dtype)} for col in df.columns]
        }
    except Exception:
        profile = None

    return {
        "session": dict(session),
        "messages": messages,
        "profile": profile
    }

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    try:
        # Save file to data directory
        filepath = os.path.join(DATA_DIR, f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Test loading it
        if filepath.endswith(".csv"):
            df = pd.read_csv(filepath)
        elif filepath.endswith((".xls", ".xlsx")):
            df = pd.read_excel(filepath)
        else:
            os.remove(filepath)
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV or Excel file.")
            
        # Create session in DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO sessions (filename, filepath) VALUES (?, ?)", (file.filename, filepath))
        session_id = c.lastrowid
        conn.commit()
        conn.close()
        
        profile = {
            "rows": len(df),
            "cols": len(df.columns),
            "columns": [{"name": col, "type": str(df[col].dtype)} for col in df.columns]
        }
        
        return {
            "session_id": session_id,
            "filename": file.filename, 
            "message": "File uploaded successfully!",
            "profile": profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

class ChatRequest(BaseModel):
    session_id: int
    prompt: str
    model_name: str = "llama3:8b"

@app.post("/api/chat")
def chat(request: ChatRequest):
    session_id = request.session_id
    prompt = request.prompt
    model_name = request.model_name
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filepath FROM sessions WHERE id = ?", (session_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
        
    filepath = row[0]
    
    # Save user message
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "user", prompt))
    conn.commit()
    conn.close()
    
    try:
        # Load dataset
        if filepath.endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
            
        # Load the LLM
        llm = ChatOllama(model=model_name, temperature=0, num_ctx=8192)
        
        # Fetch last 4 messages (2 turns) to keep context small
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 5", (session_id,))
        history_rows = c.fetchall()
        history_rows.reverse()
        conn.close()
        
        history_rows = history_rows[:-1] # exclude the current prompt we just inserted
        context_str = ""
        import re
        if history_rows:
            context_str = "Recent Conversation History:\n"
            for r, text in history_rows:
                # Remove old chart markdowns from history so the AI doesn't hallucinate them
                clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', text).strip()
                context_str += f"{r.capitalize()}: {clean_text}\n"
            context_str += "\n"
            
        augmented_prompt = context_str + "New Question: " + prompt
        
        chart_filename = f"chart_{int(datetime.now().timestamp())}.png"

        # Instruct agent to save charts locally if needed
        prefix_instructions = (
            "You are working with a pandas dataframe in Python. "
            "If the user asks for a plot or chart, just use matplotlib or seaborn to create it. "
            "Do NOT worry about saving the image yourself, the system will save it automatically. "
            "CRITICAL: Always use the exact tool name 'Action: python_repl_ast' when executing code. "
            "Do not invent new tool names."
        )

        pandas_df_agent = create_pandas_dataframe_agent(
            llm,
            df,
            verbose=True,
            agent_type="zero-shot-react-description",
            allow_dangerous_code=True,
            prefix=prefix_instructions,
            max_iterations=10,
            max_execution_time=300,
            agent_executor_kwargs={"handle_parsing_errors": True},
            number_of_head_rows=3
        )
        
        response = pandas_df_agent.invoke(augmented_prompt)
        assistant_response = response["output"]
        
        # Auto-save any charts created by the agent
        import matplotlib.pyplot as plt
        if plt.get_fignums():
            chart_path = os.path.join(CHARTS_DIR, chart_filename)
            plt.savefig(chart_path)
            plt.clf()
            plt.close('all')
            # Ensure the image markdown is in the response (routes to the separate charts mount)
            assistant_response += f"\n\n![chart](/static/charts/{chart_filename})"
        
        # Save assistant message
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "assistant", assistant_response))
        conn.commit()
        conn.close()
        
        return {"response": assistant_response}
    except Exception as e:
        error_msg = f"I'm sorry, I couldn't process your request. Error details: {str(e)}"
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "assistant", error_msg))
        conn.commit()
        conn.close()
        
        return {"response": error_msg}

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time
    
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run server
    uvicorn.run(app, host="127.0.0.1", port=8000)