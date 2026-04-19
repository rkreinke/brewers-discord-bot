import discord
from discord.ext import commands, tasks
import requests
import json
import os
import re

# =====================
# CONFIG
# =====================

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1495328350468702248
TEAM_ID = 158

DATA_FILE = "state.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# =====================
# STATE (no duplicates EVER)
# =====================
def load_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"last_id": None}


def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f)


state = load_state()


# =====================
# FETCH DATA
# =====================
def fetch():
    url = "https://statsapi.mlb.com/api/v1/transactions"

    params = {
        "teamId": TEAM_ID,
        "limit": 5
    }

    r = requests.get(url, params=params)
    data = r.json()

    if "transactions" not in data:
        return None

    t = data["transactions"][0]

    return {
        "id": t.get("transactionId"),
        "text": t.get("description", "")
    }


# =====================
# MOVE TYPE DETECTOR (ELITE)
# =====================
def detect_type(text):
    t = text.lower()

    if "optioned" in t or "sent down" in t:
        return "🔻 Optioned to Minors"
    if "recalled" in t or "called up" in t:
        return "🟢 Called Up"
    if "traded" in t:
        return "🔁 Trade"
    if "designated for assignment" in t or "dfa" in t:
        return "🔴 DFA"
    if "injured" in t or "il" in t:
        return "🟡 Injured List"
    return "⚪ Transaction"


# =====================
# PLAYER NAME EXTRACTION (SMART)
# =====================
def extract_player(text):
    # usually first capitalized name in sentence
    match = re.findall(r"[A-Z][a-z]+ [A-Z][a-z]+", text)
    return match[0] if match else "Unknown Player"


# =====================
# TEAM INFERENCE (REAL IMPROVEMENT)
# =====================
MINOR_LEAGUE_TEAMS = [
    "Nashville", "Sounds", "Biloxi", "Shuckers",
    "Wisconsin", "Mudcats", "Timber Rattlers",
    "Carolina", "Bulls", "AAA", "AA", "A+"
]


def infer_from_to(text):
    t = text

    from_team = None
    to_team = None

    for team in MINOR_LEAGUE_TEAMS:
        if team in t:
            if "from" in t.lower():
                from_team = team
            if "to" in t.lower():
                to_team = team

    # fallback logic
    if "Brewers" in t:
        if "optioned" in t.lower():
            to_team = "Minor League Affiliate"
            from_team = "Milwaukee Brewers"
        if "recalled" in t.lower():
            from_team = "Minor League Affiliate"
            to_team = "Milwaukee Brewers"

    return from_team, to_team


# =====================
# BOT READY
# =====================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    check.start()


# =====================
# MAIN LOOP
# =====================
@tasks.loop(minutes=2)
async def check():
    global state

    move = fetch()
    if not move:
        return

    if move["id"] == state["last_id"]:
        return

    state["last_id"] = move["id"]
    save_state(state)

    text = move["text"]

    player = extract_player(text)
    move_type = detect_type(text)
    from_team, to_team = infer_from_to(text)

    embed = discord.Embed(
        title="🚨 Brewers Roster Move",
        description=f"**{player}**\n{text}",
        color=0x00ff7f
    )

    embed.add_field(name="Move Type", value=move_type, inline=False)

    if from_team:
        embed.add_field(name="From", value=from_team, inline=True)

    if to_team:
        embed.add_field(name="To", value=to_team, inline=True)

    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)


# =====================
# TEST COMMAND
# =====================
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


bot.run(TOKEN)