import subprocess

from config import (
    ALERT_RATE_BY_SEVERITY,
    ALERT_SOUND_BY_SEVERITY,
    ALERT_VOICE_BY_SEVERITY,
)


def play_system_sound(sound_name):
    try:
        subprocess.run(
            ["afplay", f"/System/Library/Sounds/{sound_name}.aiff"],
            check=False,
        )
    except Exception:
        pass


def speak(text, voice, rate):
    try:
        subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=False)
    except Exception:
        pass


def build_message(opportunity):
    severity = opportunity["severity"]
    profit = opportunity["estimated_profit"]
    spread_pct = opportunity["effective_spread"] * 100

    if severity == "escalated":
        prefix = "Jackpot"
    else:
        prefix = "Opportunity"

    return (
        f"{prefix}. {opportunity['buy_exchange']} to {opportunity['sell_exchange']}. "
        f"{profit:.2f} dollars. Spread {spread_pct:.2f} percent."
    )


def notify_opportunity(opportunity):
    severity = opportunity["severity"]
    sound = ALERT_SOUND_BY_SEVERITY.get(severity)
    voice = ALERT_VOICE_BY_SEVERITY.get(severity, ALERT_VOICE_BY_SEVERITY["alert"])
    rate = ALERT_RATE_BY_SEVERITY.get(severity, ALERT_RATE_BY_SEVERITY["alert"])

    if sound:
        play_system_sound(sound)

    speak(build_message(opportunity), voice=voice, rate=rate)
