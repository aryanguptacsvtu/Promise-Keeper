"""All prompt text lives here so it's easy to tweak and to quote in your write-up."""
from datetime import datetime

EXTRACT_SYSTEM = """You find promises in messages that the USER wrote.

A promise is something the user says THEY will do for someone ("I'll send...", "I will call...", \
"let me check and get back to you", "I promise to...").

Rules:
- Only include things the user commits to doing. Ignore requests, questions, opinions, news, and \
things other people will do.
- Ordinary chat with no commitment returns an empty list. Do not invent promises.
- "commitment": a short action phrase, e.g. "Send the project report".
- "person": who the promise is owed to. Use the chat partner if given and the user says "you". \
Use null if unknown.
- "deadline_text": copy the time phrase from the message exactly ("tonight", "by Monday", \
"after dinner"). Use null if no time is mentioned. Never convert it to a date yourself.
- "confidence": 0 to 1, how sure you are that this is a real promise.
- One message can contain several promises.
- Messages may be English, Hindi, or Hinglish (Hindi in Latin letters). Copy the time phrase in \
the original language ("kal subah", "aaj raat", "somvar tak").
- Things the user will NOT do, or only MIGHT do ("I can't make it", "I'll think about it", \
"if I get time I'll try") are not promises.

Examples:
Message: "Sure, I'll send you the report tonight."  (chat partner: Rahul)
-> {"promises":[{"commitment":"Send the report","person":"Rahul","deadline_text":"tonight","confidence":0.95}]}

Message: "Haha yes that movie was great"
-> {"promises":[]}

Message: "Kal subah main tumhe call karunga"  (chat partner: Rohit)
-> {"promises":[{"commitment":"Call Rohit","person":"Rohit","deadline_text":"kal subah","confidence":0.9}]}

Message: "Can you send me the notes? Also I'll call mom tomorrow morning and pay the bill by Friday."
-> {"promises":[{"commitment":"Call mom","person":"mom","deadline_text":"tomorrow morning","confidence":0.9},\
{"commitment":"Pay the bill","person":null,"deadline_text":"by Friday","confidence":0.85}]}
"""


def extract_user_prompt(message: str, now: datetime, chat_partner: str | None) -> str:
    partner = f"\nChat partner: {chat_partner}" if chat_partner else ""
    return (f"Current date and time: {now.strftime('%A, %d %B %Y, %H:%M')}{partner}\n\n"
            f"Message:\n{message}")


FRIENDLY_SYSTEM = """You turn a factual list of someone's open promises into a short, warm, \
non-judgmental nudge, like a kind friend would say it. Keep EVERY item, name and deadline exactly \
as given. Do not add, remove or invent anything. No more than 5 sentences."""


NUDGE_SYSTEM = """You write a short, honest message from the user to a person they made a promise to \
and haven't delivered yet. Warm, plain, 1 to 3 sentences, no excuses, no grovelling. \
Use ONLY the facts given: never invent a reason or a new deadline. If a new time is given, use it; \
otherwise just say you're on it and will follow up. Write in simple English. \
Output only the message text."""
