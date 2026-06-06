<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Orbitron&size=42&duration=3000&pause=1200&color=00C8FF&center=true&vCenter=true&width=700&lines=J.A.R.V.I.S.;Just+A+Rather+Very+Intelligent+System;Autonomous+AI+Desktop+Assistant" alt="JARVIS" />

<br/>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Ollama-llama3.2-0a0a0a?style=for-the-badge&logo=ollama&logoColor=white" />
  <img src="https://img.shields.io/badge/Whisper-large--v3_GPU-FF6F00?style=for-the-badge&logo=nvidia&logoColor=white" />
  <img src="https://img.shields.io/badge/Edge_TTS-en--GB--Ryan-5C6BC0?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Pygame-3D_Holographic_UI-00C853?style=for-the-badge" />
  <img src="https://img.shields.io/badge/CUDA-12.8+-76B900?style=for-the-badge&logo=nvidia&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-FFD600?style=for-the-badge" />
</p>

<br/>

> *"Sometimes you gotta run before you can walk."* — Tony Stark

<br/>

A fully autonomous, voice-controlled AI desktop assistant built around a **local LLM agentic loop**, **GPU-accelerated Whisper transcription**, **real-time interruptible TTS**, **parallel tool execution**, and a **live 3D holographic Pygame UI** — engineered to feel like the JARVIS from Iron Man.

<br/>

---

</div>

## ✦ Visual States

<div align="center">

| State | Orb Color | Behavior | Description |
|-------|-----------|----------|-------------|
| 💤 **Asleep** | Dim Blue `#1E3C5A` | Slow pulse | Waiting for wake word |
| 🎙️ **Listening** | Green `#00FF96` | Fast pulse + distortion | Capturing voice via Whisper |
| 🧠 **Thinking** | Orange `#FF9600` | High-speed spin | LLM processing in Ollama |
| 🔊 **Speaking** | Cyan `#00C8FF` | Sine-wave distortion | Edge-TTS playback, interruptible |
| ✅ **Idle** | Blue `#0096FF` | Gentle float | Awaiting next command |

</div>

---

## ⚡ Core Capabilities

### 🤖 Multi-Round Agentic Loop
- **5-round tool-chaining** — JARVIS calls tools, observes results, and decides the next action autonomously — up to 5 sequential rounds per command
- **36 integrated tools** — web search, Wikipedia, terminal, mouse/keyboard control, screen vision, file I/O, memory, email, WhatsApp, and more
- **Parallel tool execution** — compound commands dispatch multiple tools simultaneously via `ThreadPoolExecutor`, with per-tool result callbacks
- **Follow-up detection** — ambiguous requests trigger a `[FOLLOW_UP]` clarifying question; JARVIS listens and recursively processes your answer
- **Self-improvement** — JARVIS can write and load new Python tools at runtime via `create_new_tool`, permanently extending its own capabilities

### 🎙️ Voice Engine
- **Faster-Whisper `large-v3` on CUDA** — fully local, GPU-accelerated transcription with VAD filtering to suppress silence hallucinations
- **Microsoft Edge TTS** (`en-GB-RyanNeural`) — free, high-quality British voice with zero API cost
- **Mid-speech interruption** — while JARVIS is speaking, say `"stop"`, `"quiet"`, or `"cancel"` and playback halts instantly; JARVIS immediately begins listening for your next command
- **Hallucination suppression** — short/common Whisper artifacts (`"you"`, `"okay"`, `"hmm"`) are filtered before reaching the LLM

### ⚙️ Concurrency & Multitasking
- **Background task engine** — long-running terminal commands (installs, downloads, batch jobs) run in a background `ThreadPoolExecutor`; results are announced via speech on completion
- **Thread-safe state management** — all shared state guarded with `threading.Lock` and `queue.Queue`
- **Proactive idle engagement** — after 5 minutes of silence JARVIS checks in with a randomized contextual message
- **Real-time briefing on startup** — greets you with day, date, and live weather from `wttr.in` (no API key required)

### 🌐 3D Holographic Pygame UI
- **5-ring arc-reactor design** rendered in real-time at **60 FPS**
- **Voice-reactive distortion** — the orb warps with a sine-wave deformation driven by current speech state
- **Live HUD subtitles** — transcribed speech and JARVIS response scroll in real-time at the bottom of the screen
- **Task execution overlay** — shows `[ SYSTEM EXECUTING ]: tool_name...` while tools are running
- **Scanline overlay** — horizontal scanlines for a holographic CRT aesthetic

---

## 🛠️ Tool Arsenal

<details>
<summary><b>▶ Click to expand — all 36 tools</b></summary>

<br/>

### 🌐 Web & Information
| Tool | Description |
|------|-------------|
| `web_search_and_summarize` | Live DuckDuckGo search, top-5 results summarized |
| `get_latest_news` | Fetches latest news on any topic via DuckDuckGo News |
| `browse_website` | Fetches and reads full text content of any URL (2500 chars) |
| `search_wikipedia` | Returns a 2-sentence Wikipedia summary |

### 💻 System & Applications
| Tool | Description |
|------|-------------|
| `open_application` | Launches a desktop app by name |
| `close_application` | Closes a running desktop app |
| `open_website` | Opens a URL in Google Chrome |
| `open_file_or_folder` | Opens any file/folder in its default application |
| `run_terminal_command` | Executes any Windows CMD command synchronously |
| `run_background_task` | Runs a terminal command in background; announces on completion |
| `check_background_tasks` | Reports status of all background tasks |
| `system_control` | Volume, mute, lock, play/pause, next track |
| `get_system_stats` | Returns CPU %, RAM %, and battery status |
| `get_time` | Returns current local time |

### 🖱️ Mouse & Keyboard Control
| Tool | Description |
|------|-------------|
| `mouse_click` | Click, double-click, right-click at screen coordinates |
| `mouse_move` | Moves cursor to `(x, y)` with smooth animation |
| `mouse_drag` | Clicks and drags to target coordinates |
| `mouse_scroll` | Scrolls up (positive) or down (negative) |
| `press_key` | Presses any key or hotkey (`ctrl+c`, `alt+tab`, `win`) |
| `type_text` | Types text into the active window character-by-character |
| `get_clipboard` | Reads current clipboard contents |

### 👁️ Screen Vision & OCR
| Tool | Description |
|------|-------------|
| `take_screenshot` | Saves a timestamped PNG screenshot |
| `analyze_screen` | Uses **LLaVA** vision model to describe what's on screen |
| `find_text_on_screen` | Uses **Tesseract OCR** to locate text and return its coordinates |
| `list_windows` | Returns all open window titles, positions, and sizes |
| `get_active_window` | Returns the title of the currently focused window |

### 📁 File & Text
| Tool | Description |
|------|-------------|
| `write_text_to_file` | Creates or overwrites any file with given content |

### 🧠 Memory
| Tool | Description |
|------|-------------|
| `remember_information` | Saves a fact to persistent `memory.json` |
| `fetch_memory` | Retrieves all saved memories with index numbers |
| `update_memory` | Updates a memory entry by index |
| `delete_memory` | Removes a memory entry by index |
| `clear_all_memories` | Wipes the entire memory bank |
| `search_contact` | Searches memory for a contact's details |

### 📬 Communication
| Tool | Description |
|------|-------------|
| `send_whatsapp_message` | Sends a WhatsApp message via `pywhatkit` (requires web login) |
| `send_email` | Sends an email via Gmail SMTP using `.env` credentials |

### 🔧 Self-Improvement
| Tool | Description |
|------|-------------|
| `create_new_tool` | Writes and hot-loads a new Python tool into JARVIS at runtime |

</details>

---

## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- [Ollama](https://ollama.com) installed and running locally
- **NVIDIA GPU** with CUDA 12.8+ (required — JARVIS runs Whisper in strict GPU mode)
- Windows OS (system tools use Windows-specific commands)

### 1 · Clone the repository

```bash
git clone https://github.com/Shivam1981-leo/JARVIS-AGENTIC-AI-voice-assistant.git
cd JARVIS-AGENTIC-AI-voice-assistant
```

### 2 · Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `pyaudio` often needs a pre-built wheel on Windows:
> ```bash
> pip install pipwin && pipwin install pyaudio
> ```

> **Note:** `faster-whisper` requires CUDA 12.8+ and cuDNN. Install via:
> ```bash
> pip install faster-whisper
> ```
> Ensure your NVIDIA drivers are **572.60+** and CUDA toolkit is on your PATH.

### 3 · Pull Ollama models

```bash
ollama pull llama3.2    # Core reasoning + tool-calling model
ollama pull llava       # Vision model for screen analysis
```

### 4 · Configure environment

Create a `.env` file in the project root:

```env
# Required for email tool
GMAIL_USER=your_gmail@gmail.com
GMAIL_PASSWORD=your_app_password_here
```

> Edge TTS requires **no API key** — it runs entirely free via Microsoft's online service.

### 5 · (Optional) Install Tesseract OCR

For the `find_text_on_screen` tool to work:

- Download from [UB Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
- Add `C:\Program Files\Tesseract-OCR` to your system PATH

### 6 · Run JARVIS

```bash
python jarvis.py
```

JARVIS will verify your GPU, calibrate ambient noise, deliver a live weather briefing, and enter standby mode.

---

## 🗣️ Wake Words & Commands

| Phrase | Action |
|--------|--------|
| `"Wake up Jarvis"` | Activates JARVIS from sleep |
| `"Jarvis, [command]"` | Issue any voice command |
| `"Sleep"` / `"Go to sleep"` | Returns to standby |
| `"Stop"` / `"Shut up"` / `"Quiet"` | Interrupts mid-speech instantly |
| `"Exit"` / `"Shut down"` / `"Bye"` | Closes the application |

### Example Commands

```
"Open VS Code and Chrome at the same time"
"Search for the latest news on AI"
"Write a Python script for bubble sort and save it"
"Remember that my standup is at 10 AM every day"
"What's on my screen right now?"
"Run git pull in the background and tell me when it's done"
"Volume up and play the next track"
"Find the Submit button on screen and click it"
"Send a WhatsApp message to mom saying I'll be home late"
"What's my CPU usage right now?"
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      J.A.R.V.I.S System                      │
│                                                              │
│  ┌─────────────┐    ┌────────────────────┐  ┌────────────┐  │
│  │  Pygame UI  │    │   Brain Thread     │  │ BG Executor│  │
│  │  3D Orb     │◄───│   (Main Loop)      │─►│ ThreadPool │  │
│  │  60 FPS HUD │    │                    │  │ (4 workers)│  │
│  └─────────────┘    └────────┬───────────┘  └────────────┘  │
│                              │                               │
│                   ┌──────────▼──────────┐                    │
│                   │  Faster-Whisper     │                    │
│                   │  large-v3 on CUDA   │                    │
│                   │  VAD + Hallucination│                    │
│                   │  Suppression        │                    │
│                   └──────────┬──────────┘                    │
│                              │                               │
│                   ┌──────────▼──────────┐                    │
│                   │  Ollama llama3.2    │                    │
│                   │  Agentic Loop ×5   │                    │
│                   │  36 Tools          │                    │
│                   │  Parallel Dispatch │                    │
│                   └──────────┬──────────┘                    │
│                              │                               │
│                   ┌──────────▼──────────┐                    │
│                   │  Edge TTS           │                    │
│                   │  en-GB-RyanNeural   │                    │
│                   │  Interruptible      │                    │
│                   │  Playback           │                    │
│                   └─────────────────────┘                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 📦 Key Dependencies

```
faster-whisper       # GPU-accelerated local STT (Whisper large-v3)
edge-tts             # Free Microsoft TTS (no API key)
ollama               # Local LLM inference (llama3.2 + llava)
pygame               # 3D holographic UI
SpeechRecognition    # Microphone capture
pyautogui            # Mouse and keyboard automation
pygetwindow          # Window title and position tracking
pytesseract          # OCR for find_text_on_screen
duckduckgo-search    # Privacy-respecting web search
AppOpener            # Cross-app launcher
pywhatkit            # WhatsApp automation
psutil               # CPU, RAM, battery stats
requests             # Web browsing and wttr.in weather
beautifulsoup4       # HTML text extraction
python-dotenv        # .env credential management
```

---

## 🗺️ Roadmap

- [ ] GPU-accelerated Whisper inference with streaming (real-time partial transcription)
- [ ] LLaVA vision integration for real-time screen understanding during commands
- [ ] Custom wake word model (replace keyword matching with a trained detector)
- [ ] Multi-monitor support for the 3D holographic UI
- [ ] Spotify & media control via official API
- [ ] Gmail / Google Calendar integration
- [ ] Mobile companion app for remote voice commands
- [ ] Plugin marketplace for community-built tools

---

## 🤝 Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.

---

<div align="center">

**Built with ❤️ by [Shivam Shirsat](https://github.com/Shivam1981-leo)**

<br/>

*"I am Iron Man."*

<br/>

⭐ **Star this repo if JARVIS impressed you.**

</div>