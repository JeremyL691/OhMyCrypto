import subprocess
import os

def play_system_sound(sound_name="Glass"):
    # Mac has built-in sounds at /System/Library/Sounds/
    # Options: Glass, Bottle, Funk, Hero, Ping, Submarine
    try:
        subprocess.run(["afplay", f"/System/Library/Sounds/{sound_name}.aiff"], check=False)
    except Exception:
        pass

def speak(text, emotion="neutral"):
    # Mac built-in Text-to-Speech
    # Voice options: 
    #   'Alex' (Neutral, Standard)
    #   'Fred' (Robot, Sci-Fi)
    #   'Samantha' (Siri-like, Clear)
    #   'Cellos' (Singing voice, very funny)
    
    voice = "Samantha"  # Default
    rate = "175"        # Speed
    
    if emotion == "excited":
        voice = "Good News" # Or 'Cellos' for fun
        rate = "200"
    elif emotion == "bored":
        voice = "Alex"
        rate = "150"
        
    cmd = ["say", "-v", voice, "-r", rate, text]
    
    try:
        subprocess.run(cmd, check=False)
    except Exception:
        pass

def notify_opportunity(profit, spread_pct):
    # Logic to decide "Emotion" based on profit size
    
    # Thresholds
    BIG_PROFIT = 5.0  # $5 profit
    HUGE_PROFIT = 20.0 # $20 profit
    
    if profit > HUGE_PROFIT:
        # Super Excited
        play_system_sound("Ping")
        msg = f"Jackpot! Huge opportunity. {profit:.2f} dollars."
        speak(msg, emotion="excited")
        
    elif profit > BIG_PROFIT:
        # Normal Excited
        play_system_sound("Glass")
        msg = f"Money detected. {profit:.2f} dollars."
        speak(msg, emotion="neutral")
        
    else:
        # Ignore small profits to avoid noise, or just beep
        # play_system_sound("Bottle")
        pass