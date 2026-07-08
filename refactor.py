import re

with open('src/main.py', 'r') as f:
    content = f.read()

# 1. Add DATABASE_URL logic and DB class
db_class = '''
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
            c.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    filename TEXT,
                    filepath TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            \'\'\')
            c.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            \'\'\')
        else:
            c.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    filepath TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            \'\'\')
            c.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            \'\'\')
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
'''

content = re.sub(
    r'# Database initialization.*?def init_db\(\):.*?init_db\(\)', 
    db_class + '\n\nDB.init()', 
    content, 
    flags=re.DOTALL
)

content = re.sub(
    r'def get_sessions\(\):.*?return {"sessions": sessions}',
    '''def get_sessions():
    sessions = DB.execute("SELECT * FROM sessions ORDER BY created_at DESC", fetchall=True)
    return {"sessions": sessions or []}''',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'conn = sqlite3\.connect\(DB_PATH\)\s+conn\.row_factory = sqlite3\.Row\s+c = conn\.cursor\(\)\s+c\.execute\("SELECT \* FROM sessions WHERE id = \?", \(session_id,\)\)\s+session = c\.fetchone\(\)\s+if not session:\s+conn\.close\(\)\s+raise HTTPException\(status_code=404, detail="Session not found"\)\s+c\.execute\("SELECT role, content FROM messages WHERE session_id = \? ORDER BY id ASC", \(session_id,\)\)\s+messages = \[dict\(row\) for row in c\.fetchall\(\)\]\s+conn\.close\(\)',
    '''session = DB.execute("SELECT * FROM sessions WHERE id = ?", (session_id,), fetchone=True)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = DB.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,), fetchall=True) or []''',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'# Create session in DB.*?conn\.close\(\)',
    '''# Create session in DB
        session_id = DB.execute("INSERT INTO sessions (filename, filepath) VALUES (?, ?)", (file.filename, filepath), commit=True, insert=True)''',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'conn = sqlite3\.connect\(DB_PATH\)\s+c = conn\.cursor\(\)\s+c\.execute\("SELECT filepath FROM sessions WHERE id = \?", \(session_id,\)\)\s+row = c\.fetchone\(\)\s+if not row:\s+conn\.close\(\)\s+raise HTTPException\(status_code=404, detail="Session not found"\)\s+filepath = row\[0\]\s+# Save user message\s+c\.execute\("INSERT INTO messages \(session_id, role, content\) VALUES \(\?, \?, \?\)", \(session_id, "user", prompt\)\)\s+conn\.commit\(\)\s+conn\.close\(\)',
    '''row = DB.execute("SELECT filepath FROM sessions WHERE id = ?", (session_id,), fetchone=True)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    filepath = row['filepath'] if isinstance(row, dict) else row[0]
    
    # Save user message
    DB.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "user", prompt), commit=True)''',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'# Fetch last 4 messages.*?conn = sqlite3\.connect\(DB_PATH\).*?conn\.close\(\)',
    '''# Fetch last 4 messages (2 turns) to keep context small
        history_rows = DB.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 5", (session_id,), fetchall=True) or []
        history_rows = [(r['role'], r['content']) for r in history_rows] if history_rows else []
        history_rows.reverse()''',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'# Save assistant message.*?conn\.close\(\)',
    '''# Save assistant message
        DB.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "assistant", assistant_response), commit=True)''',
    content,
    flags=re.DOTALL
)

content = re.sub(
    r'conn = sqlite3\.connect\(DB_PATH\)\s+c = conn\.cursor\(\)\s+c\.execute\("INSERT INTO messages \(session_id, role, content\) VALUES \(\?, \?, \?\)", \(session_id, "assistant", error_msg\)\)\s+conn\.commit\(\)\s+conn\.close\(\)',
    '''DB.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "assistant", error_msg), commit=True)''',
    content,
    flags=re.DOTALL
)

with open('src/main.py', 'w') as f:
    f.write(content)

print("Refactored main.py")
