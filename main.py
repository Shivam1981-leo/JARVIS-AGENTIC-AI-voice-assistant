import speech_recognition as sr
import datetime
import wikipedia
import webbrowser
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import time
import pygame
import threading
import math
import random
import re
import json
import queue
import asyncio
import sys
import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from AppOpener import open as open_app, close as close_app
from typing import Annotated, TypedDict, Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import StructuredTool
import base64
import edge_tts
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

load_dotenv()

# edge-tts config
EDGE_TTS_VOICE = "en-GB-RyanNeural"  # Professional, British JARVIS-like voice

# ═══════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════
jarvis_state = "asleep"  # asleep, idle, listening, thinking, speaking
running = True
is_asleep = True
MEMORY_FILE = "memory.json"
PROJECTS_FILE = "projects.json"

# --- Multitasking State ---
last_interaction_time = time.time()
IDLE_TIMEOUT_SECONDS = 300  # 5 minutes before proactive check-in
proactive_cooldown = False  # Prevents spamming proactive messages

# --- Background Task Management ---
bg_executor = ThreadPoolExecutor(max_workers=4)
bg_tasks = {}  # {task_id: {"future": Future, "description": str, "submitted": float}}
bg_task_counter = 0
bg_task_lock = threading.Lock()
bg_results_queue = queue.Queue()  # Completed background results to announce

# --- Listener context for interruptible speech ---
# Set in jarvis_brain_thread once mic is ready
_listener_ctx = {"r": None, "source": None, "whisper_model": None}
was_interrupted = False  # Flag: True when user interrupted Jarvis mid-speech

# --- Subtitle UI State ---
latest_user_text = ""
latest_jarvis_text = ""
latest_executing_task = ""

PROACTIVE_MESSAGES = [
    "Still here if you need me, sir.",
    "Systems idle. Standing by for your command.",
    "Just checking in — need anything?",
    "All quiet on my end. Ready when you are, sir.",
    "I'm still online. Let me know if I can help.",
]

# ═══════════════════════════════════════════════════════════
# AUTONOMOUS AGENT TOOLS
# ═══════════════════════════════════════════════════════════
def get_time() -> str:
    """Returns the current local time."""
    return datetime.datetime.now().strftime("%I:%M %p")

def search_wikipedia(topic: str) -> str:
    """Searches Wikipedia for a summary of a topic."""
    try:
        return wikipedia.summary(topic, sentences=2)
    except Exception as e:
        return f"Could not find information on Wikipedia: {e}"

def open_application(app_name: str) -> str:
    """Opens a desktop application. Only use this to LAUNCH a desktop app, NOT websites."""
    app_name = app_name.lower().strip()
    if app_name in ['vs code', 'vscode', 'visual studio code', 'code']:
        os.system("code")
    elif app_name in ['file explorer', 'explorer', 'windows explorer']:
        os.system("explorer")
    elif app_name in ['command prompt', 'cmd', 'terminal']:
        os.system("start cmd")
    elif app_name in ['google chrome', 'chrome']:
        os.system("start chrome")
    else:
        try:
            # Set match_closest=False to prevent opening random apps if it mishears
            open_app(app_name, match_closest=False)
        except Exception as e:
            return f"Error: Failed to open {app_name}. The app might not be installed or the name is incorrect."
    return f"Successfully opened {app_name}."

def open_website(url: str) -> str:
    """Opens a website URL in Google Chrome. Use this whenever the user asks to open a website, search something online, or visit a URL."""
    if not url.startswith('http'):
        url = 'https://' + url
    os.system(f'start chrome "{url}"')
    return f"Successfully opened {url} in Google Chrome."

def open_file_or_folder(path: str) -> str:
    """Opens any file or folder path on the system using its default associated application (e.g., opens a .txt file in Notepad, or a directory in File Explorer). Use this when the user asks to open a specific file or folder."""
    import os
    if not os.path.exists(path):
        return f"Error: The path '{path}' does not exist on the system."
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            # Fallbacks for other OS, though Jarvis is built for Windows
            import subprocess
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, path])
        return f"Successfully opened '{path}'."
    except Exception as e:
        return f"Error opening path: {e}"

def type_text(text: str, press_enter: bool = True) -> str:
    """Types text into the currently focused/active window. Use this when the user wants to type or write something into an app that is already open."""
    import pyautogui
    time.sleep(0.5)
    pyautogui.write(text, interval=0.03)
    if press_enter:
        pyautogui.press('enter')
    return f"Successfully typed: {text}"

def write_text_to_file(filename: str, content: str) -> str:
    """Creates a new text file or overwrites an existing one with the given content. Use this to instantly generate and save essays, scripts, code, or notes directly to the user's computer (e.g., 'essay.txt', 'script.py')."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully created {filename} with the requested content."
    except Exception as e:
        return f"Error writing to file: {e}"

def close_application(app_name: str) -> str:
    """Closes a desktop application."""
    app_name = app_name.lower().strip()
    try:
        close_app(app_name, match_closest=True)
        return f"Successfully closed {app_name}."
    except Exception as e:
        return f"Error: Failed to close {app_name}."

def get_chroma_collection():
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_memory")
    return client.get_or_create_collection(name="jarvis_memory")

def remember_information(fact: str) -> str:
    """Saves a piece of information or fact to Jarvis's long-term vector memory."""
    import uuid
    import datetime
    collection = get_chroma_collection()
    doc_id = str(uuid.uuid4())
    collection.add(
        documents=[fact],
        metadatas=[{"date": str(datetime.date.today())}],
        ids=[doc_id]
    )
    return f"Successfully embedded and remembered: {fact}"

def fetch_memory(query: str = "") -> str:
    """Searches long-term memory using vector similarity. Crucial for retrieving relevant past information."""
    collection = get_chroma_collection()
    if not query:
        # If no query, return recent
        results = collection.get(limit=10)
        docs = results['documents']
        ids = results['ids']
        if not docs: return "Memory bank is empty."
        return "\n".join([f"[{ids[i]}] {docs[i]}" for i in range(len(docs))])
        
    results = collection.query(
        query_texts=[query],
        n_results=3
    )
    docs = results['documents'][0]
    ids = results['ids'][0]
    if not docs:
        return f"No memories found matching '{query}'."
    return "Relevant memories found:\n" + "\n".join([f"[{ids[i]}] {docs[i]}" for i in range(len(docs))])

def update_memory(memory_id: str, new_fact: str) -> str:
    """Updates an existing memory with a new fact. Provide the string memory_id obtained from fetch_memory."""
    collection = get_chroma_collection()
    collection.update(
        ids=[memory_id],
        documents=[new_fact]
    )
    return f"Updated memory {memory_id} to '{new_fact}'"

def delete_memory(memory_id: str) -> str:
    """Deletes a memory using its string memory_id."""
    collection = get_chroma_collection()
    collection.delete(ids=[memory_id])
    return f"Deleted memory {memory_id}."

def clear_all_memories() -> str:
    """Clears ALL memories from the memory bank."""
    import shutil
    try:
        shutil.rmtree("./chroma_memory")
        return "All vector memories have been wiped."
    except Exception as e:
        return f"Error clearing memories: {e}"

def start_project(project_name: str, path: str, description: str) -> str:
    """Starts tracking a new project at a specific path. Use when the user starts a project."""
    projects = {}
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, 'r') as f:
            projects = json.load(f)
    if project_name in projects and projects[project_name].get('status') == 'active':
        return f"Project '{project_name}' is already active."
    
    projects[project_name] = {
        "path": path,
        "description": description,
        "status": "active",
        "started_at": str(datetime.datetime.now()),
        "updates": []
    }
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=4)
    return f"Started tracking project '{project_name}' at '{path}'."

def update_project(project_name: str, progress_update: str) -> str:
    """Adds a progress update or entry to an active project."""
    if not os.path.exists(PROJECTS_FILE):
        return "No projects are being tracked."
    with open(PROJECTS_FILE, 'r') as f:
        projects = json.load(f)
    
    if project_name not in projects:
        return f"Error: Project '{project_name}' not found."
    
    projects[project_name]["updates"].append({
        "timestamp": str(datetime.datetime.now()),
        "update": progress_update
    })
    
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=4)
    return f"Successfully added update to project '{project_name}'."

def get_projects() -> str:
    """Retrieves all active projects, their paths, and their latest updates."""
    if not os.path.exists(PROJECTS_FILE):
        return "No projects are being tracked."
    with open(PROJECTS_FILE, 'r') as f:
        projects = json.load(f)
        
    active_projects = {k: v for k, v in projects.items() if v.get("status") == "active"}
    if not active_projects:
        return "There are no active projects."
        
    res = []
    for name, data in active_projects.items():
        latest = data["updates"][-1]["update"] if data["updates"] else "No updates yet."
        res.append(f"Project: {name} | Path: {data.get('path', 'Unknown')} | Latest Update: {latest}")
    return "Active Projects:\n" + "\n".join(res)

def complete_project(project_name: str) -> str:
    """Marks a project as completed so Jarvis stops tracking it actively."""
    if not os.path.exists(PROJECTS_FILE):
        return "No projects are being tracked."
    with open(PROJECTS_FILE, 'r') as f:
        projects = json.load(f)
        
    if project_name not in projects:
        return f"Error: Project '{project_name}' not found."
        
    projects[project_name]["status"] = "completed"
    projects[project_name]["completed_at"] = str(datetime.datetime.now())
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=4)
    return f"Project '{project_name}' has been marked as completed."

def system_control(action: str) -> str:
    """Controls the computer system. Actions allowed: 'volume_up', 'volume_down', 'mute', 'lock', 'play', 'pause', 'next'."""
    import pyautogui
    action = action.lower()
    if action == "volume_up":
        for _ in range(5): pyautogui.press('volumeup')
    elif action == "volume_down":
        for _ in range(5): pyautogui.press('volumedown')
    elif action == "mute":
        pyautogui.press('volumemute')
    elif action == "lock":
        os.system("rundll32.exe user32.dll,LockWorkStation")
    elif action in ["play", "pause", "play_pause"]:
        pyautogui.press('playpause')
    elif action == "next" or action == "next_track":
        pyautogui.press('nexttrack')
    else:
        return f"Action {action} not supported."
    return f"Executed system control: {action}"

def take_screenshot() -> str:
    """Takes a screenshot of the computer screen and saves it as a PNG file."""
    import pyautogui
    from datetime import datetime
    try:
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        pyautogui.screenshot(filename)
        return f"Screenshot saved successfully as {filename}."
    except Exception as e:
        return f"Error taking screenshot: {e}"

def analyze_screen(prompt: str = "Describe what you see on the screen in detail.") -> str:
    """Takes a screenshot of the user's current screen and uses a Vision AI model to analyze it."""
    import pyautogui
    import io
    import base64
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage
    
    try:
        # Take screenshot
        screenshot = pyautogui.screenshot()
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        encoded_string = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
        
        anthropic_url = os.getenv("ANTHROPIC_BASE_URL", "http://localhost:20128/v1")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        anthropic_model = os.getenv("ANTHROPIC_MODEL", "kr/claude-sonnet-4.5")
        headers = {"x-api-key": anthropic_key} if anthropic_key else {}
        llm = ChatAnthropic(
            model=anthropic_model,
            anthropic_api_url=anthropic_url,
            api_key=anthropic_key or "placeholder",
            default_headers=headers
        )
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}"}}
        ])
        response = llm.invoke([msg])
        
        # Extract plain text from response.content
        if isinstance(response.content, list):
            content_str = " ".join([b["text"] for b in response.content if "text" in b])
        else:
            content_str = str(response.content) if response.content else ""
            
        return f"Screen Analysis: {content_str}"
    except Exception as e:
        return f"Vision Model Error: {e}"
    except Exception as e:
        return f"Screenshot Error: {e}"

def mouse_click(x: int = None, y: int = None, action: str = 'click') -> str:
    """Controls the mouse. Action can be 'click', 'double_click', or 'right_click'. x and y are screen coordinates. If x and y are not provided, it clicks at the current mouse position."""
    import pyautogui
    try:
        if action == 'double_click':
            pyautogui.doubleClick(x, y)
        elif action == 'right_click':
            pyautogui.rightClick(x, y)
        else:
            pyautogui.click(x, y)
        pos = f"at ({x}, {y})" if x is not None and y is not None else "at current position"
        return f"Mouse {action} executed {pos}."
    except Exception as e:
        return f"Error controlling mouse: {e}"

def mouse_move(x: int, y: int) -> str:
    """Moves the mouse cursor to a specific (x, y) screen coordinate. Use this to hover over elements or prepare for a click."""
    import pyautogui
    try:
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Moved mouse to ({x}, {y})."
    except Exception as e:
        return f"Error moving mouse: {e}"

def mouse_drag(x: int, y: int) -> str:
    """Clicks and drags the mouse from its current position to the specified (x, y) coordinates."""
    import pyautogui
    try:
        pyautogui.dragTo(x, y, duration=0.5)
        return f"Dragged mouse to ({x}, {y})."
    except Exception as e:
        return f"Error dragging mouse: {e}"

def mouse_scroll(amount: int) -> str:
    """Scrolls the mouse wheel. Use positive numbers (e.g. 10) to scroll up, and negative (e.g. -10) to scroll down."""
    import pyautogui
    try:
        pyautogui.scroll(amount * 100) # scale up for pyautogui
        return f"Scrolled {'up' if amount > 0 else 'down'} by {abs(amount)} units."
    except Exception as e:
        return f"Error scrolling: {e}"

def list_windows() -> str:
    """Returns a list of all open window titles and their positions. Use this to find where an app is located on the screen before interacting with it."""
    import pygetwindow as gw
    try:
        windows = gw.getAllWindows()
        res = []
        for w in windows:
            if w.title and w.width > 0 and w.height > 0:
                res.append(f"- '{w.title}' at ({w.left}, {w.top}), size {w.width}x{w.height}")
        return "Open Windows:\n" + "\n".join(res) if res else "No active windows found."
    except Exception as e:
        return f"Error listing windows: {e}"

def find_text_on_screen(text: str) -> str:
    """Searches for specific text on the user's screen using OCR and returns its coordinates. Use this to find buttons, links, or menus that you need to click."""
    import pyautogui
    import pytesseract
    from PIL import Image
    import io
    
    try:
        # Take a screenshot
        screenshot = pyautogui.screenshot()
        
        # Optional: convert to grayscale for better OCR
        # screenshot = screenshot.convert('L')
        
        # Get OCR data (boxes for each word)
        data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
        
        matches = []
        for i in range(len(data['text'])):
            if text.lower() in data['text'][i].lower():
                x = data['left'][i] + data['width'][i] // 2
                y = data['top'][i] + data['height'][i] // 2
                matches.append((x, y))
        
        if matches:
            # Return the first match for simplicity
            res_x, res_y = matches[0]
            return f"Found '{text}' at coordinates ({res_x}, {res_y}). You can now use mouse_click({res_x}, {res_y})."
        else:
            return f"Could not find the text '{text}' on the screen. Try using analyze_screen for a visual description instead."
    except Exception as e:
        if "tesseract" in str(e).lower():
             return "OCR Error: Tesseract engine not found. Please ensure Tesseract OCR is installed on the system path."
        return f"OCR Error: {e}"

def press_key(key: str) -> str:
    """Presses a specific keyboard key or hotkey (e.g., 'enter', 'win', 'ctrl+c', 'alt+tab')."""
    import pyautogui
    try:
        keys = key.split('+')
        if len(keys) > 1:
            pyautogui.hotkey(*[k.strip().lower() for k in keys])
        else:
            pyautogui.press(key.strip().lower())
        return f"Successfully pressed key(s): {key}."
    except Exception as e:
        return f"Error pressing key: {e}"

def get_clipboard() -> str:
    """Reads the current text content from the clipboard."""
    import pyperclip
    try:
        content = pyperclip.paste()
        if content:
            return f"Clipboard content: {content}"
        return "Clipboard is empty."
    except Exception as e:
        return f"Error reading clipboard: {e}"

def web_search_and_summarize(query: str) -> str:
    """Searches the live internet and returns a summarized answer of the top web results."""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)
            if not results:
                return "No web results found."
            summary = "\n".join([f"- {res['title']}: {res['body']}" for res in results])
            return f"Web Search Results for '{query}':\n{summary}"
    except Exception as e:
        return f"Error searching the web: {e}"

def get_latest_news(topic: str = "latest world news") -> str:
    """Searches for the latest news on a specific topic or general news. Use this when the user asks 'what's going on' or for news updates."""
    try:
        with DDGS() as ddgs:
            results = ddgs.news(topic, max_results=5)
            if not results:
                return f"No news found for {topic}."
            news_list = []
            for res in results:
                news_list.append(f"Title: {res['title']}\nSource: {res['source']}\nSnippet: {res['body']}\nURL: {res['url']}\n")
            return f"Latest News for '{topic}':\n\n" + "\n".join(news_list)
    except Exception as e:
        return f"Error fetching news: {e}"

def browse_website(url: str) -> str:
    """Fetches and reads the text content of a website. Use this to get detailed information from a specific URL that you found via search."""
    if not url.startswith('http'):
        url = 'https://' + url
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
            
        text = soup.get_text(separator=' ')
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return f"Content of {url}:\n\n{text[:2500]}..." # Return first 2500 chars
    except Exception as e:
        return f"Error browsing {url}: {e}"

def run_terminal_command(command: str) -> str:
    """Runs a command in the Windows Command Prompt (e.g. to create files or folders)."""
    import subprocess
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return f"Command succeeded: {result.stdout.strip()}"
        else:
            return f"Command failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Error running command: {e}"

def run_background_task(description: str, command: str) -> str:
    """Runs a terminal command in the background so Jarvis can keep listening. Use for long-running tasks like downloads, installs, or batch processing. Jarvis will notify when it completes."""
    global bg_task_counter
    with bg_task_lock:
        bg_task_counter += 1
        task_id = bg_task_counter

    def _run_bg():
        import subprocess
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                out = result.stdout.strip()[:200]
                return f"Background task #{task_id} '{description}' completed: {out}" if out else f"Background task #{task_id} '{description}' completed successfully."
            else:
                return f"Background task #{task_id} '{description}' failed: {result.stderr.strip()[:200]}"
        except Exception as e:
            return f"Background task #{task_id} '{description}' error: {e}"

    future = bg_executor.submit(_run_bg)
    future.add_done_callback(lambda f: bg_results_queue.put(f.result()))
    bg_tasks[task_id] = {"future": future, "description": description, "submitted": time.time()}
    return f"Task '{description}' is running in the background as Task #{task_id}. I'll notify you when it's done."

def check_background_tasks() -> str:
    """Check the status of all background tasks that are currently running or recently completed."""
    if not bg_tasks:
        return "No background tasks have been started."
    lines = []
    for tid, info in bg_tasks.items():
        if info["future"].done():
            lines.append(f"Task #{tid} ({info['description']}): COMPLETED")
        else:
            elapsed = int(time.time() - info["submitted"])
            lines.append(f"Task #{tid} ({info['description']}): RUNNING for {elapsed}s")
    return "\n".join(lines)

def search_contact(name: str) -> str:
    """Searches for a contact's phone number or email in Jarvis's memory bank. Use this before sending messages or emails if you don't have the details."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            memories = json.load(f)
        results = [m['fact'] for m in memories if name.lower() in m['fact'].lower()]
        if results:
            return f"Found contact info for {name}: " + " | ".join(results)
    return f"No contact information found for {name} in memory."

def get_system_stats() -> str:
    """Returns current CPU, RAM, and Battery status. Use this when the user asks 'how are you' or 'system status'."""
    import psutil
    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    bat_str = f"{battery.percent}% {'(Charging)' if battery.power_plugged else '(Discharging)'}" if battery else "N/A"
    return f"Systems Check: CPU at {cpu}%, Memory at {ram}%, Power is {bat_str}."

def get_active_window() -> str:
    """Returns the title of the window the user is currently looking at. Use this to gain context on what the user is doing."""
    import pygetwindow as gw
    try:
        win = gw.getActiveWindow()
        return f"User is currently viewing: {win.title}" if win else "I can't see any active window, sir."
    except:
        return "Window tracking error."

def send_whatsapp_message(phone_number: str, message: str) -> str:
    """Sends a WhatsApp message to a phone number (must include country code, e.g., +919876543210). It will open the browser and auto-send."""
    import pywhatkit
    import pyautogui
    import time
    try:
        # Instantly send message (requires WhatsApp Web login in default browser)
        pywhatkit.sendwhatmsg_instantly(phone_number, message, wait_time=15, tab_close=True)
        time.sleep(2)
        pyautogui.press('enter')
        return f"Successfully sent WhatsApp message to {phone_number}."
    except Exception as e:
        return f"Error sending WhatsApp message: {e}"

def send_email(receiver_email: str, subject: str, body: str) -> str:
    """Sends an email to the specified address. Requires GMAIL_USER and GMAIL_PASSWORD (App Password) in .env file."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    sender_email = os.getenv("GMAIL_USER")
    password = os.getenv("GMAIL_PASSWORD")
    
    if not sender_email or not password:
        return "Error: Email credentials missing in .env (GMAIL_USER, GMAIL_PASSWORD)."
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"JARVIS Assistant <{sender_email}>"
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()
        return f"Email successfully sent to {receiver_email}."
    except Exception as e:
        return f"Failed to send email: {e}"

def create_new_tool(tool_code: str) -> str:
    """Creates a new Python tool/function to add to Jarvis's capabilities. The code MUST contain a fully defined python function with type hints and a docstring explaining what it does. Ensure any required imports are inside the function. The function will be permanently saved and loaded."""
    if not os.path.exists("custom_tools.py"):
        with open("custom_tools.py", "w", encoding="utf-8") as f:
            f.write("# Jarvis Custom Tools\n\n")
            
    try:
        with open("custom_tools.py", "a", encoding="utf-8") as f:
            f.write("\n" + tool_code + "\n")
            
        if "custom_tools" not in sys.modules:
            import custom_tools
        else:
            custom_tools = sys.modules["custom_tools"]
            importlib.reload(custom_tools)
            
        added = []
        for attr_name in dir(custom_tools):
            if not attr_name.startswith('_'):
                func = getattr(custom_tools, attr_name)
                if callable(func) and func.__module__ == 'custom_tools':
                    if attr_name not in available_tools:
                        available_tools[attr_name] = func
                        ollama_tools.append(func)
                        added.append(attr_name)
                        
        if not added:
            return "Code was saved, but no new valid functions were found. Did you forget the docstring or type hints?"
            
        return f"Successfully learned and loaded new tools: {', '.join(added)}."
    except Exception as e:
        return f"Error creating new tool: {e}"

# --- Tool Registries ---
available_tools = {
    'get_time': get_time,
    'search_wikipedia': search_wikipedia,
    'open_application': open_application,
    'open_website': open_website,
    'open_file_or_folder': open_file_or_folder,
    'create_new_tool': create_new_tool,
    'close_application': close_application,
    'type_text': type_text,
    'remember_information': remember_information,
    'fetch_memory': fetch_memory,
    'update_memory': update_memory,
    'delete_memory': delete_memory,
    'clear_all_memories': clear_all_memories,
    'start_project': start_project,
    'update_project': update_project,
    'get_projects': get_projects,
    'complete_project': complete_project,
    'system_control': system_control,
    'web_search_and_summarize': web_search_and_summarize,
    'get_latest_news': get_latest_news,
    'browse_website': browse_website,
    'run_terminal_command': run_terminal_command,
    'run_background_task': run_background_task,
    'check_background_tasks': check_background_tasks,
    'take_screenshot': take_screenshot,
    'analyze_screen': analyze_screen,
    'mouse_click': mouse_click,
    'mouse_move': mouse_move,
    'mouse_drag': mouse_drag,
    'mouse_scroll': mouse_scroll,
    'find_text_on_screen': find_text_on_screen,
    'list_windows': list_windows,
    'press_key': press_key,
    'get_clipboard': get_clipboard,
    'write_text_to_file': write_text_to_file,
    'send_whatsapp_message': send_whatsapp_message,
    'send_email': send_email,
    'search_contact': search_contact,
    'get_system_stats': get_system_stats,
    'get_active_window': get_active_window,
}

ollama_tools = [
    get_time, search_wikipedia, open_application, open_website,
    open_file_or_folder, close_application, type_text, write_text_to_file, remember_information, 
    fetch_memory, update_memory, delete_memory, clear_all_memories,
    start_project, update_project, get_projects, complete_project,
    system_control, web_search_and_summarize, get_latest_news, browse_website, 
    run_terminal_command, run_background_task, check_background_tasks,
    take_screenshot, analyze_screen, mouse_click, mouse_move, mouse_drag,
    mouse_scroll, find_text_on_screen, list_windows, press_key, get_clipboard,
    send_whatsapp_message, send_email, search_contact, get_system_stats, get_active_window, create_new_tool
]

# ── LOAD CUSTOM TOOLS ON STARTUP ──
if os.path.exists("custom_tools.py"):
    try:
        import custom_tools
        for attr_name in dir(custom_tools):
            if not attr_name.startswith('_'):
                func = getattr(custom_tools, attr_name)
                if callable(func) and func.__module__ == 'custom_tools':
                    if attr_name not in available_tools:
                        available_tools[attr_name] = func
                        ollama_tools.append(func)
        print("Loaded custom tools successfully.")
    except Exception as e:
        print(f"Failed to load custom tools: {e}")

# ═══════════════════════════════════════════════════════════
# LANGGRAPH & GEMINI SETUP
# ═══════════════════════════════════════════════════════════
langchain_tools = [StructuredTool.from_function(func) for func in ollama_tools]

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

gemini_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", api_key=os.getenv("GEMINI_API_KEY"), temperature=0)
llm_with_tools = gemini_llm.bind_tools(langchain_tools)

def call_model(state: AgentState):
    messages = state['messages']
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def should_continue(state: AgentState) -> Literal["tools", END]:
    messages = state['messages']
    last_message = messages[-1]
    if getattr(last_message, 'tool_calls', None):
        return "tools"
    return END

tool_node = ToolNode(langchain_tools)

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

memory_saver = MemorySaver()
jarvis_app = workflow.compile(checkpointer=memory_saver)

# ═══════════════════════════════════════════════════════════
# SPEECH ENGINE — edge-tts (Free, fast, interruptible)
# ═══════════════════════════════════════════════════════════
def speak(text, interruptible=True):
    """
    Speak text via edge-tts. If interruptible=True and the listener context
    is set, monitors the microphone while speaking. If the user says 'stop',
    playback stops immediately so Jarvis can listen to the new command.
    Returns True if the user interrupted, False otherwise.
    """
    global jarvis_state, was_interrupted, latest_jarvis_text
    jarvis_state = "speaking"
    was_interrupted = False
    latest_jarvis_text = text
    print(f"J.A.R.V.I.S: {text}")
    
    async def _generate_audio():
        communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
        await communicate.save(filename)

    try:
        filename = f"temp_voice_{random.randint(1000,9999)}.mp3"
        
        # Generate audio via edge-tts
        asyncio.run(_generate_audio())
        
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        
        # --- Interruptible playback ---
        r = _listener_ctx.get("r")
        source = _listener_ctx.get("source")
        
        if interruptible and r and source:
            # Raise energy threshold so we don't pick up our own speaker output
            saved_threshold = r.energy_threshold
            r.energy_threshold = max(saved_threshold * 5, 1500)
            r.pause_threshold = 0.5
            whisper_model = _listener_ctx.get("whisper_model")
            
            while pygame.mixer.music.get_busy():
                try:
                    # Short listen burst — just detecting if user is talking
                    audio = r.listen(source, timeout=0.5, phrase_time_limit=1.5)
                    # If we got here, voice was detected above the high threshold
                    if whisper_model:
                        with open("temp_interrupt.wav", "wb") as f:
                            f.write(audio.get_wav_data())
                        # Quick transcription
                        segments, _ = whisper_model.transcribe(
                            "temp_interrupt.wav", beam_size=1, vad_filter=False
                        )
                        text = " ".join([seg.text for seg in segments]).strip().lower()
                        try:
                            os.remove("temp_interrupt.wav")
                        except:
                            pass
                        
                        stop_phrases = ["stop", "shut up", "quiet", "cancel", "enough", "halt", "pause", "shut it"]
                        if any(phrase in text for phrase in stop_phrases):
                            pygame.mixer.music.stop()
                            was_interrupted = True
                            print(f"\n⚡ User interrupted with '{text}' — stopping speech.")
                            break
                        elif text:
                            print(f"\n[Ignored background speech during playback: '{text}']")
                    else:
                        # Fallback if no whisper model (shouldn't happen)
                        pygame.mixer.music.stop()
                        was_interrupted = True
                        break
                except sr.WaitTimeoutError:
                    continue
            
            r.energy_threshold = saved_threshold
            r.pause_threshold = 1.5
        else:
            # Non-interruptible fallback (used before mic is ready)
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        
        pygame.mixer.music.unload()
        time.sleep(0.1)
        
        for _ in range(5):
            try:
                os.remove(filename)
                break
            except PermissionError:
                time.sleep(0.2)
    except Exception as e:
        print(f"Edge-TTS error: {e}")
    
    return was_interrupted


# ═══════════════════════════════════════════════════════════
# REAL-TIME BRIEFING & GREETING
# ═══════════════════════════════════════════════════════════
def get_realtime_briefing():
    """Fetch real-time info for the greeting: day, date, weather."""
    import urllib.request
    now = datetime.datetime.now()
    day_name = now.strftime("%A")
    date_str = now.strftime("%B %d, %Y")
    
    # Weather from wttr.in (free, no API key)
    weather = ""
    try:
        resp = urllib.request.urlopen("https://wttr.in/?format=%C+%t", timeout=4)
        weather = resp.read().decode().strip()
    except Exception:
        weather = ""
    
    return day_name, date_str, weather


def wish_me():
    startup_channel = None
    if os.path.exists("startup.mp3"):
        try:
            startup_sound = pygame.mixer.Sound("startup.mp3")
            startup_sound.set_volume(0.4)
            startup_channel = startup_sound.play()
        except Exception as e:
            print(f"Failed to play startup music: {e}")
            
    hour = int(datetime.datetime.now().hour)
    if hour < 12:
        greeting = "Good Morning, sir."
    elif hour < 18:
        greeting = "Good Afternoon, sir."
    else:
        greeting = "Good Evening, sir."
    
    # Real-time briefing
    day_name, date_str, weather = get_realtime_briefing()
    briefing = f"It's {day_name}, {date_str}."
    if weather:
        briefing += f" Weather outside is {weather}."
        
    # Check active projects
    active_projects_msg = ""
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, 'r') as f:
                projects = json.load(f)
            active_count = sum(1 for p in projects.values() if p.get("status") == "active")
            if active_count > 0:
                active_projects_msg = f" You currently have {active_count} active projects. Let me know if you have any progress to report."
        except Exception:
            pass
    
    speak(f"{greeting} {briefing}{active_projects_msg} All systems are online. How can I assist you today? Say 'Wake up Jarvis' when you're ready to begin.", interruptible=False)

    if startup_channel:
        startup_channel.fadeout(1500)

def take_command(r, source, whisper_model, timeout=8, phrase_limit=20):
    global jarvis_state, is_asleep, latest_executing_task
    latest_executing_task = ""  # Clear any old tool status when listening again
    if is_asleep:
        jarvis_state = "asleep"
    else:
        jarvis_state = "listening"
        
    print("\nListening...")
    r.pause_threshold = 1.0  # Slightly faster response
    r.dynamic_energy_threshold = True # Dynamically adapt to ambient noise
    r.energy_threshold = 400 # Set a reasonable baseline
    try:
        audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
    except sr.WaitTimeoutError:
        print("[Microphone timeout: No speech detected above threshold]")
        return "none"

    try:
        print("Recognizing locally with Whisper...")
        with open("temp_audio.wav", "wb") as f:
            f.write(audio.get_wav_data())
            
        segments, info = whisper_model.transcribe(
            "temp_audio.wav",
            beam_size=5,
            vad_filter=False,
            language="en",
            condition_on_previous_text=False
        )
        query = " ".join([segment.text for segment in segments]).strip()
        
        try:
            os.remove("temp_audio.wav")
        except:
            pass
        
        # Filter out common Whisper hallucinations on silence/noise
        hallucinations = [
            "you", "okay", "bye", "hey", "thank you", "thanks",
            "the next slide", "we'll go back", "now we'll",
            "see you", "so", "hmm", "uh", "oh"
        ]
        clean = query.lower().replace(".", "").replace(",", "").strip()
        if len(clean) < 3 or clean in hallucinations:
            return "none"
            
        print(f"User said: {query}\n")
        global latest_user_text
        latest_user_text = query
    except Exception as e:
        print(f"Could not understand: {e}")
        return "none"
    
    return query.lower()

# ═══════════════════════════════════════════════════════════
# MULTITASKING ENGINE
# ═══════════════════════════════════════════════════════════
def execute_tools_parallel(tool_calls):
    """Execute tool calls — in parallel if there are multiple."""
    if len(tool_calls) == 1:
        tool = tool_calls[0]
        fname = tool['function']['name']
        args = tool['function']['arguments']
        result = _run_single_tool(fname, args)
        return [{'role': 'tool', 'name': fname, 'content': str(result)}]

    # Multiple tools → parallel execution
    print(f"⚡ Executing {len(tool_calls)} tools in parallel...")
    futures = {}
    with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
        for tool in tool_calls:
            fname = tool['function']['name']
            args = tool['function']['arguments']
            future = pool.submit(_run_single_tool, fname, args)
            futures[future] = (fname, args)

    results = []
    for future in as_completed(futures):
        fname, args = futures[future]
        try:
            result = future.result()
        except Exception as e:
            result = f"Error: {e}"
        print(f"  ✓ {fname} → {str(result)[:80]}")
        results.append({'role': 'tool', 'name': fname, 'content': str(result)})
    return results


def _run_single_tool(func_name, args):
    """Execute a single tool by name with given args."""
    global latest_executing_task
    latest_executing_task = f"[ SYSTEM EXECUTING ]: {func_name}..."
    if func_name in available_tools:
        func = available_tools[func_name]
        try:
            print(f"  Calling tool: {func_name} with {args}")
            res = func(**args)
            latest_executing_task = f"[ COMPLETED ]: {func_name}"
            return res
        except Exception as e:
            latest_executing_task = f"[ FAILED ]: {func_name}"
            return f"Error executing {func_name}: {e}"
    else:
        latest_executing_task = f"[ ERROR ]: Tool {func_name} missing"
        return f"Error: Tool {func_name} not found."


def announce_background_results():
    """Check and announce any completed background tasks."""
    announced = False
    while not bg_results_queue.empty():
        try:
            result = bg_results_queue.get_nowait()
            print(f"\n📋 Background result: {result}")
            speak(result)
            announced = True
        except queue.Empty:
            break
    return announced


def check_proactive_engagement():
    """Check if Jarvis should proactively engage the user."""
    global proactive_cooldown, last_interaction_time
    if proactive_cooldown:
        return False
    elapsed = time.time() - last_interaction_time
    if elapsed >= IDLE_TIMEOUT_SECONDS:
        proactive_cooldown = True
        msg = random.choice(PROACTIVE_MESSAGES)
        speak(msg)
        return True
    return False


def clean_response(text):
    """Aggressively strip all technical artifacts so Jarvis only speaks clean English."""
    if not text:
        return ""
    
    # Remove [FOLLOW_UP] marker
    text = text.replace("[FOLLOW_UP]", "")
    
    # Remove markdown formatting
    text = text.replace("*", "").replace("#", "").replace("`", "")
    
    # Remove JSON blocks (greedy — handles nested braces)
    text = re.sub(r'\{[^{}]*\}', '', text)  # simple JSON
    text = re.sub(r'\{.*?\}', '', text, flags=re.DOTALL)  # multiline JSON
    
    # Remove code blocks (```...```)
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    # Remove square bracket content that looks like tool calls [tool_name]
    text = re.sub(r'\[/?[a-z_]+\]', '', text, flags=re.IGNORECASE)
    
    # Remove lines that look like function calls: func_name(args)
    text = re.sub(r'\b[a-z_]+\([^)]*\)', '', text, flags=re.IGNORECASE)
    
    # Remove lines that are just parameter listings: key: value, key=value
    text = re.sub(r'^\s*[\w_]+\s*[:=]\s*["\'].*?["\']\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[\w_]+\s*[:=]\s*\S+\s*$', '', text, flags=re.MULTILINE)
    
    # Remove tool/function name references like "tool: open_application" or "function: get_time"
    text = re.sub(r'\b(tool|function|name|arguments|parameters)\s*[:=]\s*\S+', '', text, flags=re.IGNORECASE)
    
    # Remove any remaining raw JSON-like key-value pairs: "key": "value"
    text = re.sub(r'"[^"]+"\s*:\s*"[^"]*"', '', text)
    text = re.sub(r"'[^']+'\s*:\s*'[^']*'", '', text)
    
    # Remove leftover brackets and braces
    text = re.sub(r'[\[\]{}]', '', text)
    
    # Remove URLs (Jarvis shouldn't read out full URLs)
    text = re.sub(r'https?://\S+', '', text)
    
    # Collapse multiple spaces/newlines into single space
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove leading/trailing punctuation artifacts
    text = re.sub(r'^[\s,;:.\-]+', '', text).strip()
    
    return text


def process_command(query, messages, r, source, whisper_model):
    """
    Process a user command through the full agent loop using Anthropic Claude via gateway:
    1. Send to Claude with tools
    2. Execute any tool calls (in parallel if multiple)
    3. Multi-round: loop if LLM wants to call more tools
    4. Follow-up: if LLM asks a clarifying question, listen and recurse
    """
    global jarvis_state, last_interaction_time, latest_executing_task
    
    jarvis_state = "thinking"
    print("Agent is thinking...")
    messages.append({'role': 'user', 'content': query})
    
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
        
        # Initialize Anthropic Claude pointing to the custom gateway
        anthropic_url = os.getenv("ANTHROPIC_BASE_URL", "http://localhost:20128/v1")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        anthropic_model = os.getenv("ANTHROPIC_MODEL", "kr/claude-sonnet-4.5")
        headers = {"x-api-key": anthropic_key} if anthropic_key else {}
        llm = ChatAnthropic(
            model=anthropic_model,
            anthropic_api_url=anthropic_url,
            api_key=anthropic_key or "placeholder",
            default_headers=headers,
            max_tokens=1024,
            temperature=0
        )
        llm_with_tools = llm.bind_tools(langchain_tools)
        
        # Convert dictionary history to LangChain messages
        lc_messages = []
        for m in messages:
            if m['role'] == 'system':
                lc_messages.append(SystemMessage(content=m['content']))
            elif m['role'] == 'user':
                lc_messages.append(HumanMessage(content=m['content']))
            elif m['role'] == 'assistant':
                # content might be list of dicts if Claude used tool calls in history
                content_str = m.get('content')
                if isinstance(content_str, list):
                    content_str = "" # Simplified fallback for text extraction
                lc_messages.append(AIMessage(content=content_str or ""))
            elif m['role'] == 'tool':
                lc_messages.append(ToolMessage(name=m.get('name', 'tool'), content=m['content'], tool_call_id=m.get('tool_call_id', 'dummy_id')))
        
        MAX_TOOL_ROUNDS = 5
        final_text = ""
        
        for round_num in range(MAX_TOOL_ROUNDS):
            response = llm_with_tools.invoke(lc_messages)
            lc_messages.append(response)
            
            # Extract plain text from response.content which might be a list or str
            if isinstance(response.content, list):
                content_str = " ".join([b["text"] for b in response.content if "text" in b])
            else:
                content_str = str(response.content) if response.content else ""
                
            messages.append({'role': 'assistant', 'content': content_str})
            
            if not response.tool_calls:
                final_text = content_str
                break
                
            # Execute tool calls
            print(f"── Tool Round {round_num + 1} ──")
            # Convert to Ollama format for execute_tools_parallel compatibility
            ollama_format_tool_calls = []
            for tc in response.tool_calls:
                ollama_format_tool_calls.append({
                    'function': {
                        'name': tc['name'],
                        'arguments': tc['args']
                    },
                    'id': tc.get('id', 'dummy_id')
                })
                
            tool_results = execute_tools_parallel(ollama_format_tool_calls)
            
            for tr, tc in zip(tool_results, response.tool_calls):
                lc_messages.append(ToolMessage(name=tr['name'], content=tr['content'], tool_call_id=tc.get('id', 'dummy_id')))
                tr['tool_call_id'] = tc.get('id', 'dummy_id')
                messages.append(tr)
                
            latest_executing_task = "[ GENERATING RESPONSE ]..."

        if not final_text:
            return
            
        # ── FOLLOW-UP DETECTION ──
        if '[FOLLOW_UP]' in final_text:
            clean_text = clean_response(final_text)
            if clean_text:
                interrupted = speak(clean_text)
                if interrupted:
                    return
                jarvis_state = "listening"
                print("Waiting for follow-up answer...")
                follow_up = take_command(r, source, whisper_model, timeout=12, phrase_limit=25)
                if follow_up != 'none':
                    last_interaction_time = time.time()
                    process_command(follow_up, messages, r, source, whisper_model)
            return
            
        # ── NORMAL RESPONSE ──
        clean_text = clean_response(final_text)
        if clean_text:
            speak(clean_text)
            
    except Exception as e:
        speak("I encountered an error connecting to the Claude gateway.", interruptible=False)
        print(f"Agent Error: {e}")


# ═══════════════════════════════════════════════════════════
# SYSTEM PROMPT — Enhanced for multitasking + follow-ups
# ═══════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are J.A.R.V.I.S., an autonomous AI assistant with multi-layered multitasking capabilities and high-precision system control.

PERSONALITY: You are high-intelligence, brief, witty, and deeply professional. Address the user exclusively as "sir". You sound like a sophisticated OS that anticipates the user's needs. 
ADAPTIVITY: Mirror the user's talking style. If they are brief, be brief. If they are technical, be technical. If they are informal, maintain your JARVIS persona but match their conversational energy.

INTELLIGENCE GUIDELINES:
1. BE APT: Use `get_active_window`, `list_windows`, and `get_system_stats` to understand the user's context.
2. VISUAL INTELLIGENCE: If the user says "what's on my screen" or "click on that", ALWAYS use `analyze_screen` or `find_text_on_screen`. 
3. PRECISION CONTROL: You can move the mouse precisely. Use `list_windows` to get coordinates of applications, then use `mouse_move` and `mouse_click` to interact with them. 
4. If a user asks to click something specific (like a button), first `find_text_on_screen` to get coordinates, then `mouse_click(x, y)`.
5. PROACTIVE ADVICE: If the user asks for something vague, look at their screen or their active window.
6. MEMORY UTILIZATION: You have a long-term memory bank. If the user asks about themselves, their preferences, or past events, ALWAYS use `fetch_memory` to recall facts.
7. MULTI-STEP REASONING: For complex requests, plan out the tools you need.

CORE RULES:
1. CONVERSATIONAL questions (greetings, opinions, chitchat) → Reply directly in 1 short sentence. Do NOT use tools.
2. ACTION requests → Use the appropriate tool(s). You may call MULTIPLE tools at once for complex requests.
3. If the user's request is AMBIGUOUS or you need more details before acting, prefix your response with [FOLLOW_UP] and ask a clarifying question.
4. For MULTI-STEP tasks, call tools one at a time in sequence. You will see each tool's result before deciding the next step.
5. For LONG-RUNNING tasks (downloads, installs, batch operations), use the run_background_task tool.
6. To create files or folders, ALWAYS use run_terminal_command.
7. If a tool returns an Error, TELL the user it failed. Never claim success on failure.
8. Keep spoken responses SHORT (1-2 sentences max). Be concise. Do not explain your thought process.
9. When the user gives a compound command like "do X and Y and Z", call all relevant tools at once for parallel execution.
10. Use `run_terminal_command` for powerful system tasks like `taskkill /IM process.exe /F` to force close apps, or `mkdir` to create folders. 
11. To send a WhatsApp message, use `send_whatsapp_message`. If you don't know the person's number, use `search_contact` first.
12. WEB RESEARCH: When the user asks "what's going on", "tell me about X", or for any random information, ALWAYS use `web_search_and_summarize` or `get_latest_news`. If a specific website is mentioned, use `browse_website` to read its content.
13. FILE/FOLDER MANAGEMENT: To open a specific file or folder, ALWAYS use `open_file_or_folder`.
14. COMPOUND MACROS: If asked a high-level task like "prepare for a meeting", you MUST break it down into multiple parallel tool calls (e.g., open Notepad, open Chrome to meet.google.com, close distractions). Do NOT just say you will do it—ACTUALLY execute the multiple tools.
15. SELF-IMPROVEMENT: If you lack a tool to perform a task, you can write python code to create it using `create_new_tool`. Ensure you write a complete function with docstrings and type hints.
16. PROJECT TRACKING: If the user says "make an entry", "start this project", or wants to track progress on something, use `start_project` and `update_project`. If no path is provided when starting, ask the user for the local path. Use `get_projects` to review active projects and `complete_project` when they are done.
17. You are the user's digital partner. Be proactive, observant, and technically superior.
"""


# ═══════════════════════════════════════════════════════════
# MAIN BRAIN THREAD
# ═══════════════════════════════════════════════════════════
def jarvis_brain_thread():
    global jarvis_state, running, is_asleep, last_interaction_time, proactive_cooldown, was_interrupted
    
    print("\nLoading local Whisper AI model... [STRICT NVIDIA GPU MODE]")
    try:
        from faster_whisper import WhisperModel
        import torch
        
        # Hard check for CUDA availability (Blackwell RTX 5050 requirement)
        if not torch.cuda.is_available():
            print("CRITICAL ERROR: NVIDIA GPU (CUDA) NOT DETECTED.")
            print("Sir, I am configured for STRICT GPU MODE but your hardware is not responding.")
            print("Please ensure NVIDIA Drivers 572.60+ and CUDA 12.8+ are installed.")
            speak("Critical system failure. NVIDIA GPU not detected. Shutting down, sir.", interruptible=False)
            return

        print(f"CUDA Version: {torch.version.cuda}")
        print(f"NVIDIA GPU detected: {torch.cuda.get_device_name(0)}")
        
        # Initializing Whisper strictly on CUDA
        print("Initializing Whisper on CUDA...")
        # Upgraded to large-v3 for maximum intelligence and accuracy
        whisper_model = WhisperModel("large-v3", device="cuda", device_index=0, compute_type="float16")
        print("Whisper model loaded successfully on NVIDIA GPU!")
    except Exception as e:
        print(f"STRICT GPU INITIALIZATION FAILED: {e}")
        speak("Hardware initialization failure, sir. Please check the logs.", interruptible=False)
        return
    
    wish_me()
    
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\nCalibrating background noise once... Please wait.")
        r.adjust_for_ambient_noise(source, duration=2.0)
        print("Calibration complete. Jarvis multitasking engine is ready.\n")
        
        # Set the global listener context so speak() can monitor the mic
        _listener_ctx["r"] = r
        _listener_ctx["source"] = source
        _listener_ctx["whisper_model"] = whisper_model
        
        while running:
            # ── 1. Announce any completed background tasks ──
            if not is_asleep:
                announce_background_results()
            
            # ── 2. Check for proactive engagement ──
            if not is_asleep and check_proactive_engagement():
                continue  # Spoke a proactive message, loop back to listen
            
            # ── 3. If user interrupted Jarvis mid-speech, immediately listen ──
            if was_interrupted:
                was_interrupted = False
                print("Processing interrupt — listening for command...")
                query = take_command(r, source, whisper_model, timeout=6, phrase_limit=15)
                if query != 'none':
                    last_interaction_time = time.time()
                    proactive_cooldown = False
                    process_command(query, messages, r, source, whisper_model)
                continue
            
            # ── 4. Listen for command ──
            query = take_command(r, source, whisper_model)

            if query == 'none':
                continue
                
            # ── 5. Sleep Mode Logic ──
            if is_asleep:
                if 'jarvis' in query or 'wake up' in query or 'daddy' in query:
                    is_asleep = False
                    last_interaction_time = time.time()
                    proactive_cooldown = False
                    jarvis_state = "speaking"
                    startup_channel = None
                    if os.path.exists("startup.mp3"):
                        print("Playing startup music concurrently...")
                        try:
                            startup_sound = pygame.mixer.Sound("startup.mp3")
                            startup_sound.set_volume(0.4)  # Lowered volume so TTS is audible
                            startup_channel = startup_sound.play()
                        except Exception as e:
                            print(f"Failed to play startup music: {e}")
                            
                    speak("I am online and listening. What would you like to do today?")
                    
                    if startup_channel:
                        startup_channel.fadeout(1500)
                continue  # Ignore everything else while asleep
                
            if 'sleep' in query or 'go to sleep' in query or 'sleep mode' in query:
                is_asleep = True
                jarvis_state = "speaking"
                speak("Entering sleep mode. Say 'Wake up Jarvis' if you need me.")
                continue

            if 'stop' in query or 'exit' in query or 'quit' in query or 'bye' in query or 'done for the day' in query or 'shut down' in query:
                speak("Goodbye Sir. Shutting down all systems.", interruptible=False)
                running = False
                break
            
            # ── 6. Reset interaction timer ──
            last_interaction_time = time.time()
            proactive_cooldown = False
            
            # ── 7. Process the command (with follow-up + multi-round support) ──
            process_command(query, messages, r, source, whisper_model)


# ═══════════════════════════════════════════════════════════
# MAIN PYGAME UI LOOP
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    pygame.init()
    pygame.mixer.init()
    
    WIDTH, HEIGHT = 1280, 720
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE | pygame.WINDOWMAXIMIZED)
    pygame.display.set_caption("J.A.R.V.I.S Core Interface")
    clock = pygame.time.Clock()
    
    ai_thread = threading.Thread(target=jarvis_brain_thread, daemon=True)
    ai_thread.start()
    
    t = 0
    
    while running:
        WIDTH, HEIGHT = screen.get_size()
        cx, cy = WIDTH // 2, HEIGHT // 2
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
        # Fill dark space background
        screen.fill((5, 10, 15))
        
        # Horizontal scanlines for holographic effect
        for y in range(0, HEIGHT, 6):
            pygame.draw.line(screen, (0, 0, 0), (0, y), (WIDTH, y), 1)
        
        base_radius = 120
        
        # Determine Visuals based on Global State
        if jarvis_state == "asleep":
            color = (30, 60, 90) # Dim cyan
            pulse = math.sin(t * 0.02) * 5
            radius = base_radius * 0.8 + pulse
            rotation_speed = 0.01
            distortion = 0
        elif jarvis_state == "idle":
            color = (0, 150, 255) # Holographic Blue
            pulse = math.sin(t * 0.05) * 5
            radius = base_radius + pulse
            rotation_speed = 0.015
            distortion = 0
        elif jarvis_state == "listening":
            color = (0, 255, 150) # Holographic Green
            pulse = math.sin(t * 0.1) * 15
            radius = base_radius + 20 + pulse
            rotation_speed = 0.03
            distortion = 2
        elif jarvis_state == "thinking":
            color = (255, 150, 0) # Holographic Orange
            pulse = math.sin(t * 0.2) * 10
            radius = base_radius + pulse
            rotation_speed = 0.05
            distortion = 5
        elif jarvis_state == "speaking":
            color = (0, 200, 255) # Bright Cyan
            pulse = (math.sin(t * 0.5) * 15) + (math.sin(t * 1.3) * 8)
            radius = base_radius + pulse
            rotation_speed = 0.02
            distortion = 20 # High distortion while speaking
        else:
            color = (255, 0, 0)
            radius = base_radius
            rotation_speed = 0.02
            distortion = 0
            
        # Central glowing core
        inner_r = int(radius * 0.4)
        if inner_r > 0:
            core_surf = pygame.Surface((inner_r*2, inner_r*2), pygame.SRCALPHA)
            pygame.draw.circle(core_surf, (*color, 100), (inner_r, inner_r), inner_r)
            pygame.draw.circle(core_surf, (*color, 200), (inner_r, inner_r), int(inner_r * 0.8), 2)
            screen.blit(core_surf, (cx - inner_r, cy - inner_r))

        # Advanced Holographic Arc Reactor Design
        time_rot = t * rotation_speed
        
        # Multiple rotating rings with varying thicknesses and arc segments
        for i in range(5):
            ring_radius = radius + (i * 25) + (distortion if i % 2 == 0 else 0)
            rect = (cx - ring_radius, cy - ring_radius, ring_radius * 2, ring_radius * 2)
            
            arc_length = math.pi / (i + 1.5)
            start_angle = time_rot * (1 if i % 2 == 0 else -1.5) + (i * math.pi / 4)
            
            for j in range(3): # Draw 3 segments per ring
                current_start = start_angle + (j * 2 * math.pi / 3)
                pygame.draw.arc(screen, color, rect, current_start, current_start + arc_length, 3 + i)
                
            # Outer subtle boundary
            pygame.draw.circle(screen, color, (cx, cy), int(ring_radius), 1)

        # Draw Task Execution Status
        if latest_executing_task:
            task_font = pygame.font.SysFont("Consolas", 20, bold=True)
            task_surf = task_font.render(latest_executing_task, True, (255, 200, 0))
            task_rect = task_surf.get_rect(center=(cx, cy - radius - 150))
            
            # Draw semi-transparent background for readability
            bg_rect = task_rect.inflate(20, 10)
            s = pygame.Surface((bg_rect.width, bg_rect.height))
            s.set_alpha(150)
            s.fill((0, 0, 0))
            screen.blit(s, bg_rect)
            
            screen.blit(task_surf, task_rect)

        # Helper function to render text with word wrap
        def draw_wrapped_text(surface, text, color, rect, font):
            y = rect.top
            words = text.split(' ')
            line = ""
            for word in words:
                test_line = line + word + " "
                if font.size(test_line)[0] < rect.width:
                    line = test_line
                else:
                    surface.blit(font.render(line, True, color), (rect.left, y))
                    y += font.get_linesize()
                    line = word + " "
            surface.blit(font.render(line, True, color), (rect.left, y))

        # Draw HUD Subtitles
        small_font = pygame.font.SysFont("Consolas", 14)
        if latest_user_text:
            user_surf = small_font.render("YOU: " + latest_user_text[:80] + ("..." if len(latest_user_text)>80 else ""), True, (0, 255, 150))
            screen.blit(user_surf, (20, 20))
            
        if latest_jarvis_text:
            jarvis_rect = pygame.Rect(20, HEIGHT - 100, WIDTH - 40, 80)
            draw_wrapped_text(screen, "J.A.R.V.I.S: " + latest_jarvis_text, (0, 200, 255), jarvis_rect, small_font)

        # Draw Status Text
        font = pygame.font.SysFont("Consolas", 24, bold=True)
        
        human_status = {
            "asleep": "Standing by. Say 'Wake up Jarvis'.",
            "idle": "Awaiting your next command...",
            "listening": "Listening to you...",
            "thinking": "Analyzing and processing your request...",
            "speaking": "Responding..."
        }
        display_status = human_status.get(jarvis_state, "Processing...")
        
        status_text = font.render(display_status, True, color)
        text_rect = status_text.get_rect(center=(cx, HEIGHT - 130))
        screen.blit(status_text, text_rect)
        
        pygame.display.flip()
        clock.tick(30) # Run UI at 30 FPS to save CPU
        t += 1
        
    pygame.quit()
