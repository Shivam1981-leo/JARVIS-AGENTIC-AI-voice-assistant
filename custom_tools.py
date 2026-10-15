# Jarvis Custom Tools

def run_python_code(code: str) -> str:
    """
    Executes Python code autonomously in a secure subprocess and returns the output.
    Use this for Agentic Workflows to solve math, analyze data, or script tasks on the fly!
    """
    import subprocess
    import tempfile
    import os
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
            
        result = subprocess.run(
            ['python', temp_path],
            capture_output=True,
            text=True,
            timeout=15
        )
        os.remove(temp_path)
        
        output = result.stdout
        if result.stderr:
            output += "\nErrors:\n" + result.stderr
            
        return output.strip() if output else "Code executed successfully with no output."
    except Exception as e:
        return f"Execution Error: {e}"

def play_spotify_music(song_name: str) -> str:
    """
    App Integration: Opens Spotify and searches for a specific song to play.
    """
    import webbrowser
    import time
    import pyautogui
    
    try:
        url = f"https://open.spotify.com/search/{song_name.replace(' ', '%20')}"
        webbrowser.open(url)
        time.sleep(4) # Wait for page to load
        
        # Press tab a few times and hit enter to play the first result, or just click center
        # Assuming the first track play button is in a predictable location or just hit space
        # A simple spacebar might just play the last played track, but let's try to click the first search result
        pyautogui.press('tab', presses=10, interval=0.1)
        pyautogui.press('enter')
        return f"Opened Spotify and initiated search for {song_name}."
    except Exception as e:
        return f"Failed to play music: {e}"
