import speech_recognition as sr
import datetime
import wikipedia
import webbrowser
import os
import time
import pygame
import threading
import math
import random
import re
import json
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from AppOpener import open as open_app, close as close_app
import ollama
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from dotenv import load_dotenv

load_dotenv()

# ElevenLabs TTS config
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
ELEVENLABS_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George — Warm, Captivating Storyteller (JARVIS-like)

# ═══════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════
jarvis_state = "asleep"  # asleep, idle, listening, thinking, speaking
running = True
is_asleep = True
MEMORY_FILE = "memory.json"

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

def remember_information(fact: str) -> str:
    """Saves a piece of information or fact to Jarvis's long-term memory."""
    memories = []
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            memories = json.load(f)
    memories.append({"date": str(datetime.date.today()), "fact": fact})
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memories, f, indent=4)
    return f"Successfully remembered: {fact}"

def fetch_memory(query: str = "") -> str:
    """Fetches all saved memories with their index numbers. Use this to recall past information or before updating/deleting memories."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            memories = json.load(f)
        if not memories:
            return "Memory bank is empty."
        lines = []
        for i, m in enumerate(memories):
            lines.append(f"[{i}] ({m['date']}) {m['fact']}")
        return "All memories:\n" + "\n".join(lines)
    return "Memory bank is empty."

def update_memory(index: int, new_fact: str) -> str:
    """Updates an existing memory at the given index with a new fact. Use fetch_memory first to see the indices."""
    if not os.path.exists(MEMORY_FILE):
        return "Error: Memory bank is empty, nothing to update."
    with open(MEMORY_FILE, 'r') as f:
        memories = json.load(f)
    if index < 0 or index >= len(memories):
        return f"Error: Invalid index {index}. Valid range is 0 to {len(memories)-1}."
    old_fact = memories[index]['fact']
    memories[index]['fact'] = new_fact
    memories[index]['date'] = str(datetime.date.today())
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memories, f, indent=4)
    return f"Updated memory [{index}]: '{old_fact}' → '{new_fact}'"

def delete_memory(index: int) -> str:
    """Deletes a memory at the given index. Use fetch_memory first to see the indices."""
    if not os.path.exists(MEMORY_FILE):
        return "Error: Memory bank is empty, nothing to delete."
    with open(MEMORY_FILE, 'r') as f:
        memories = json.load(f)
    if index < 0 or index >= len(memories):
        return f"Error: Invalid index {index}. Valid range is 0 to {len(memories)-1}."
    removed = memories.pop(index)
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memories, f, indent=4)
    return f"Deleted memory [{index}]: '{removed['fact']}'"

def clear_all_memories() -> str:
    """Clears ALL memories from the memory bank. Only use when the user explicitly asks to wipe or reset all memories."""
    with open(MEMORY_FILE, 'w') as f:
        json.dump([], f, indent=4)
    return "All memories have been cleared."

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
    """Takes a screenshot of the user's current screen and uses a Vision AI model to analyze it. Use this when the user asks you to 'read the screen', 'look at this', or 'what am I doing'."""
    import pyautogui
    import io
    import ollama
    
    try:
        # Take screenshot
        screenshot = pyautogui.screenshot()
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        # Try to use llava for vision
        try:
            response = ollama.chat(
                model='llava',
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [img_bytes]
                }]
            )
            return f"Screen Analysis: {response['message']['content']}"
        except Exception as e:
            if "not found" in str(e).lower() or "manifest" in str(e).lower():
                return "Error: The 'llava' vision model is not installed. Please tell the user to open a terminal and run 'ollama pull llava' so you can gain the ability to see their screen."
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
    from duckduckgo_search import DDGS
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No web results found."
        summary = " ".join([res['body'] for res in results])
        return f"Web Search Summary: {summary}"
    except Exception as e:
        return f"Error searching the web: {e}"

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

# --- Tool Registries ---
available_tools = {
    'get_time': get_time,
    'search_wikipedia': search_wikipedia,
    'open_application': open_application,
    'open_website': open_website,
    'close_application': close_application,
    'type_text': type_text,
    'remember_information': remember_information,
    'fetch_memory': fetch_memory,
    'update_memory': update_memory,
    'delete_memory': delete_memory,
    'clear_all_memories': clear_all_memories,
    'system_control': system_control,
    'web_search_and_summarize': web_search_and_summarize,
    'run_terminal_command': run_terminal_command,
    'run_background_task': run_background_task,
    'check_background_tasks': check_background_tasks,
    'take_screenshot': take_screenshot,
    'analyze_screen': analyze_screen,
    'mouse_click': mouse_click,
    'press_key': press_key,
    'get_clipboard': get_clipboard,
    'write_text_to_file': write_text_to_file,
}

ollama_tools = [
    get_time, search_wikipedia, open_application, open_website,
    close_application, type_text, write_text_to_file, remember_information, 
    fetch_memory, update_memory, delete_memory, clear_all_memories,
    system_control, web_search_and_summarize, run_terminal_command,
    run_background_task, check_background_tasks,
    take_screenshot, analyze_screen, mouse_click, press_key, get_clipboard,
]

# ═══════════════════════════════════════════════════════════
# SPEECH ENGINE — ElevenLabs (Premium, interruptible)
# ═══════════════════════════════════════════════════════════
def speak(text, interruptible=True):
    """
    Speak text via ElevenLabs. If interruptible=True and the listener context
    is set, monitors the microphone while speaking. If the user says 'stop',
    playback stops immediately so Jarvis can listen to the new command.
    Returns True if the user interrupted, False otherwise.
    """
    global jarvis_state, was_interrupted, latest_jarvis_text
    jarvis_state = "speaking"
    was_interrupted = False
    latest_jarvis_text = text
    print(f"J.A.R.V.I.S: {text}")
    try:
        filename = f"temp_voice_{random.randint(1000,9999)}.mp3"
        
        # Generate audio via ElevenLabs
        audio = elevenlabs_client.text_to_speech.convert(
            text=text,
            voice_id=ELEVENLABS_VOICE,
            model_id="eleven_multilingual_v2"
        )
        save(audio, filename)
        
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
        print(f"ElevenLabs TTS error: {e}")
    
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
    if os.path.exists("startup.mp3"):
        pygame.mixer.music.load("startup.mp3")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
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
    
    speak(f"{greeting} {briefing} All systems online. Say 'Wake up Jarvis' to activate me.", interruptible=False)

def take_command(r, source, whisper_model, timeout=8, phrase_limit=20):
    global jarvis_state, is_asleep
    if is_asleep:
        jarvis_state = "asleep"
    else:
        jarvis_state = "listening"
        
    print("\nListening...")
    r.pause_threshold = 1.5
    r.energy_threshold = 300
    r.dynamic_energy_threshold = True
    try:
        audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
    except sr.WaitTimeoutError:
        return "none"

    try:
        print("Recognizing locally with Whisper...")
        with open("temp_audio.wav", "wb") as f:
            f.write(audio.get_wav_data())
            
        segments, info = whisper_model.transcribe(
            "temp_audio.wav",
            beam_size=5,
            vad_filter=True,
            language="en",
            condition_on_previous_text=False,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=300,
                threshold=0.4
            )
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
    if func_name in available_tools:
        func = available_tools[func_name]
        try:
            print(f"  Calling tool: {func_name} with {args}")
            return func(**args)
        except Exception as e:
            return f"Error executing {func_name}: {e}"
    else:
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
    Process a user command through the full agent loop:
    1. Send to Ollama with tools
    2. Execute any tool calls (in parallel if multiple)
    3. Multi-round: loop if LLM wants to call more tools
    4. Follow-up: if LLM asks a clarifying question, listen and recurse
    """
    global jarvis_state, last_interaction_time
    
    jarvis_state = "thinking"
    print("Agent is thinking...")
    messages.append({'role': 'user', 'content': query})
    
    try:
        # ── MULTI-ROUND AGENT LOOP (up to 5 rounds of tool calls) ──
        MAX_TOOL_ROUNDS = 5
        for round_num in range(MAX_TOOL_ROUNDS):
            response = ollama.chat(
                model='llama3.2',
                messages=messages,
                tools=ollama_tools
            )
            response_message = response.get('message', {})
            messages.append(response_message)
            
            # If no tool calls, we have the final answer
            if not response_message.get('tool_calls'):
                break
            
            # Execute tool calls (parallel if multiple)
            print(f"── Tool Round {round_num + 1} ──")
            tool_results = execute_tools_parallel(response_message['tool_calls'])
            messages.extend(tool_results)
            
            # After executing tools, loop back to let LLM see results
            # and potentially call more tools or give final answer
        
        # ── GET FINAL RESPONSE ──
        # If the last message was a tool result, get the LLM's final spoken response
        if messages[-1].get('role') == 'tool':
            final_response = ollama.chat(
                model='llama3.2',
                messages=messages
            )
            final_text = final_response['message']['content']
            messages.append(final_response['message'])
        else:
            final_text = response_message.get('content', '')
        
        if not final_text:
            return
        
        # ── FOLLOW-UP DETECTION ──
        # If the LLM is asking a clarifying question, speak it and listen for the answer
        if '[FOLLOW_UP]' in final_text:
            clean_text = clean_response(final_text)
            if clean_text:
                interrupted = speak(clean_text)
                if interrupted:
                    # User interrupted the question — listen for their new command
                    return  # Caller will handle the interrupt
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
            # If user interrupted, caller will handle it
            
    except Exception as e:
        speak("I encountered an error connecting to the local Ollama server.", interruptible=False)
        print(f"Agent Error: {e}")


# ═══════════════════════════════════════════════════════════
# SYSTEM PROMPT — Enhanced for multitasking + follow-ups
# ═══════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are J.A.R.V.I.S., an autonomous AI assistant with multitasking capabilities.

PERSONALITY: Speak like the JARVIS from Iron Man — brief, witty, professional. Always address the user as "sir".

CORE RULES:
1. CONVERSATIONAL questions (greetings, opinions, chitchat) → Reply directly in 1 short sentence. Do NOT use tools.
2. ACTION requests → Use the appropriate tool(s). You may call MULTIPLE tools at once for complex requests.
3. If the user's request is AMBIGUOUS or you need more details before acting, prefix your response with [FOLLOW_UP] and ask a clarifying question. Examples:
   - User: "Create a folder" → You: "[FOLLOW_UP] Where would you like me to create the folder, and what should I name it, sir?"
   - User: "Search for that thing" → You: "[FOLLOW_UP] Could you clarify what you'd like me to search for, sir?"
4. For MULTI-STEP tasks, call tools one at a time in sequence. You will see each tool's result before deciding the next step.
5. For LONG-RUNNING tasks (downloads, installs, batch operations), use the run_background_task tool so you can keep listening.
6. To create files or folders, ALWAYS use run_terminal_command.
7. If a tool returns an Error, TELL the user it failed. Never claim success on failure. If an app fails to open, tell the user the app wasn't found.
8. Keep spoken responses SHORT (1-2 sentences max). Be concise. Do not explain your thought process.
9. When the user gives a compound command like "do X and Y and Z", call all relevant tools at once for parallel execution.
10. Use `run_terminal_command` for powerful system tasks like `taskkill /IM process.exe /F` to force close apps, or `mkdir` to create folders. You have full access to the terminal.
11. If the user asks you to write an essay, code, or a long document, use `write_text_to_file` to instantly create and save it. Then use `run_terminal_command` with the `start` command (e.g., `start essay.txt`) to open and show it to the user.
"""


# ═══════════════════════════════════════════════════════════
# MAIN BRAIN THREAD
# ═══════════════════════════════════════════════════════════
def jarvis_brain_thread():
    global jarvis_state, running, is_asleep, last_interaction_time, proactive_cooldown, was_interrupted
    
    print("\nLoading local Whisper AI model... (This may take a moment on first run)")
    from faster_whisper import WhisperModel
    whisper_model = WhisperModel("medium.en", device="cpu", compute_type="int8")
    print("Whisper model loaded!")
    
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
                    speak("I am online and listening. Multitasking systems are active.")
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
    
    WIDTH, HEIGHT = 600, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("J.A.R.V.I.S Core Interface")
    clock = pygame.time.Clock()
    
    ai_thread = threading.Thread(target=jarvis_brain_thread, daemon=True)
    ai_thread.start()
    
    t = 0
    cx, cy = WIDTH // 2, HEIGHT // 2
    
    while running:
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
            
        # Draw Holographic 3D Wireframe Sphere
        time_rot = t * rotation_speed
        
        latitudes = 14
        longitudes = 28
        
        points_2d = []
        for i in range(latitudes + 1):
            lat = math.pi * i / latitudes - math.pi/2
            row = []
            for j in range(longitudes):
                lon = 2 * math.pi * j / longitudes
                
                # Base 3D coordinates
                x = math.cos(lat) * math.cos(lon)
                y = math.sin(lat)
                z = math.cos(lat) * math.sin(lon)
                
                # Apply voice distortion
                if distortion > 0:
                    dist = distortion * math.sin(lat * 8 + t * 0.3) * math.cos(lon * 8 + t * 0.3)
                    current_r = radius + dist
                else:
                    current_r = radius
                
                # Scale
                px = x * current_r
                py = y * current_r
                pz = z * current_r
                
                # Rotate around Y axis
                rx = px * math.cos(time_rot) - pz * math.sin(time_rot)
                rz = px * math.sin(time_rot) + pz * math.cos(time_rot)
                ry = py
                
                # Rotate around X axis for 3D tilt
                tilt = 0.5
                ry2 = ry * math.cos(tilt) - rz * math.sin(tilt)
                rz2 = ry * math.sin(tilt) + rz * math.cos(tilt)
                
                # Project to 2D
                fov = 500
                distance = 600
                z_proj = distance + rz2
                if z_proj > 0:
                    proj_x = cx + int(rx * fov / z_proj)
                    proj_y = cy + int(ry2 * fov / z_proj)
                    
                    # Depth fade color (brighter in front, darker in back)
                    depth_ratio = max(0.1, min(1.0, (rz2 + radius) / (2 * radius)))
                    c_r = int(color[0] * depth_ratio)
                    c_g = int(color[1] * depth_ratio)
                    c_b = int(color[2] * depth_ratio)
                    
                    row.append((proj_x, proj_y, (c_r, c_g, c_b)))
                else:
                    row.append(None)
            points_2d.append(row)
            
        # Draw wireframe lines
        for i in range(latitudes):
            for j in range(longitudes):
                p1 = points_2d[i][j]
                p2 = points_2d[i][(j+1)%longitudes] # horizontal line
                p3 = points_2d[i+1][j] # vertical line
                
                if p1 and p2:
                    pygame.draw.aaline(screen, p1[2], (p1[0], p1[1]), (p2[0], p2[1]))
                if p1 and p3:
                    pygame.draw.aaline(screen, p1[2], (p1[0], p1[1]), (p3[0], p3[1]))

        # Central glowing core
        inner_r = int(radius * 0.4)
        if inner_r > 0:
            core_surf = pygame.Surface((inner_r*2, inner_r*2), pygame.SRCALPHA)
            pygame.draw.circle(core_surf, (*color, 100), (inner_r, inner_r), inner_r)
            screen.blit(core_surf, (cx - inner_r, cy - inner_r))

        # Add outer holographic rings (HUD elements)
        ring1_r = int(radius * 1.5)
        rect1 = (cx-ring1_r, cy-ring1_r, ring1_r*2, ring1_r*2)
        pygame.draw.arc(screen, color, rect1, -time_rot, -time_rot + math.pi, 2)
        
        ring2_r = int(radius * 1.6)
        rect2 = (cx-ring2_r, cy-ring2_r, ring2_r*2, ring2_r*2)
        pygame.draw.arc(screen, color, rect2, time_rot*1.5, time_rot*1.5 + math.pi/2, 1)
        pygame.draw.arc(screen, color, rect2, time_rot*1.5 + math.pi, time_rot*1.5 + 3*math.pi/2, 1)

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
        status_text = font.render(f"STATUS: {jarvis_state.upper()}", True, color)
        text_rect = status_text.get_rect(center=(cx, HEIGHT - 130))
        screen.blit(status_text, text_rect)
        
        pygame.display.flip()
        clock.tick(60) # Run UI at 60 FPS
        t += 1
        
    pygame.quit()
