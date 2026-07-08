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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
from datetime import datetime

import sys

app = FastAPI(title="DataChat API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

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


DATABASE_URL = os.environ.get("DATABASE_URL")

class DB:
    @staticmethod
    def get_conn():
        if DATABASE_URL:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            return psycopg2.connect(DATABASE_URL), True
        else:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn, False

    @staticmethod
    def init():
        conn, is_pg = DB.get_conn()
        c = conn.cursor()
        if is_pg:
            c.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    filename TEXT,
                    filepath TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            ''')
        else:
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

    @staticmethod
    def execute(query, params=(), commit=False, fetchone=False, fetchall=False, insert=False):
        conn, is_pg = DB.get_conn()
        if is_pg:
            query = query.replace("?", "%s")
            if insert:
                query = query.rstrip("; ") + " RETURNING id"
        
        if is_pg and (fetchone or fetchall):
            from psycopg2.extras import RealDictCursor
            c = conn.cursor(cursor_factory=RealDictCursor)
        else:
            c = conn.cursor()
            
        c.execute(query, params)
        
        res = None
        if insert:
            if is_pg:
                res = c.fetchone()['id']
            else:
                res = c.lastrowid
        elif fetchone:
            row = c.fetchone()
            if row:
                res = dict(row) if not is_pg else row
        elif fetchall:
            rows = c.fetchall()
            if rows:
                res = [dict(r) for r in rows] if not is_pg else rows
            else:
                res = []
                
        if commit:
            conn.commit()
        conn.close()
        return res


DB.init()

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/api/models")
def get_models():
    """Return available NVIDIA API models."""
    return {"models": ["meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct", "nvidia/nemotron-3-ultra-550b-a55b", "gpt-4o-mini"]}

class ConnectionCheckRequest(BaseModel):
    api_key: str
    api_base_url: str = "https://integrate.api.nvidia.com/v1"

@app.post("/api/check_connection")
def check_connection(request: ConnectionCheckRequest):
    try:
        llm = ChatOpenAI(
            model="nvidia/nemotron-3-ultra-550b-a55b" if "nvidia" in request.api_base_url else "gpt-4o-mini",
            api_key=request.api_key,
            base_url=request.api_base_url,
            max_tokens=5
        )
        llm.invoke("Hi")
        return {"status": "success", "message": "Connection successful!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# (Auth endpoints removed)

@app.get("/api/sessions")
def get_sessions():
    sessions = DB.execute("SELECT * FROM sessions ORDER BY created_at DESC", fetchall=True)
    return {"sessions": sessions or []}

@app.get("/api/sessions/{session_id}")
def get_session(session_id: int):
    session = DB.execute("SELECT * FROM sessions WHERE id = ?", (session_id,), fetchone=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = DB.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,), fetchall=True) or []
    
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
        session_id = DB.execute("INSERT INTO sessions (filename, filepath) VALUES (?, ?)", (file.filename, filepath), commit=True, insert=True)
        
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

from typing import Optional

class ChatRequest(BaseModel):
    session_id: int
    prompt: str
    model_name: str = "meta/llama-3.1-70b-instruct"
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None

@app.post("/api/chat")
def chat(request: ChatRequest):
    session_id = request.session_id
    prompt = request.prompt
    model_name = request.model_name
    
    row = DB.execute("SELECT filepath FROM sessions WHERE id = ?", (session_id,), fetchone=True)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    filepath = row['filepath'] if isinstance(row, dict) else row[0]
    
    # Save user message
    DB.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "user", prompt), commit=True)
    
    try:
        # Load dataset
        if filepath.endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
            
        # Determine API Key and Base URL
        api_key = request.api_key or "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"
        base_url = request.api_base_url or "https://integrate.api.nvidia.com/v1"
        
        # Load the LLM using the appropriate API
        llm = ChatOpenAI(
            model=model_name, 
            temperature=0, 
            max_tokens=1024,
            base_url=base_url,
            api_key=api_key,
            model_kwargs={"extra_body": {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}} if "nvidia" in base_url else {}
        )
        
        # Fetch last 4 messages (2 turns) to keep context small
        history_rows = DB.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 5", (session_id,), fetchall=True) or []
        history_rows = [(r['role'], r['content']) for r in history_rows] if history_rows else []
        history_rows.reverse()
        
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

        # Use tool-calling only for OpenAI, otherwise use ReAct for Llama models
        agent_type = "tool-calling" if "gpt" in model_name else "zero-shot-react-description"

        pandas_df_agent = create_pandas_dataframe_agent(
            llm,
            df,
            verbose=True,
            agent_type=agent_type,
            allow_dangerous_code=True,
            prefix=prefix_instructions,
            max_iterations=10,
            max_execution_time=300,
            agent_executor_kwargs={"handle_parsing_errors": True},
            number_of_head_rows=3
        )
        
        import time
        max_retries = 4
        assistant_response = ""
        for attempt in range(max_retries):
            try:
                response = pandas_df_agent.invoke(augmented_prompt)
                assistant_response = response["output"]
                break
            except Exception as e:
                error_str = str(e)
                if "ResourceExhausted" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        print(f"Rate limit hit. Retrying in 10 seconds... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(10)
                        continue
                raise e
        
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
        DB.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "assistant", assistant_response), commit=True)
        
        return {"response": assistant_response}
    except Exception as e:
        error_msg = f"I'm sorry, I couldn't process your request. Error details: {str(e)}"
        
        DB.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "assistant", error_msg), commit=True)
        
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