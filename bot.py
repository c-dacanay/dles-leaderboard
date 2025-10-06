# bot.py
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import re
from datetime import date

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
print("Token loaded:", TOKEN)

# Create intents
intents = discord.Intents.default()
intents.message_content = True  # needed if you want to read message content

# Use commands.Bot instead of Client
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ {bot.user} has connected to Discord!")

# Command: !hello
@bot.command()
async def hello(ctx):
    await ctx.send(f"👋 Hello {ctx.author.display_name}! The bot is working!")

# Data storage for daily results
daily_scores = {
    "wordle": {},
    "connections": {},
    "strands": {},
    "globle": {},
}

# --- Helper to parse Connections ---
def parse_connections_result(content):
    """
    Parses a pasted NYT Connections result made of emoji squares.
    Returns a tuple: (mistakes, points, summary)
    """
    lines = content.splitlines()
    grid_lines = [l for l in lines if re.match(r"^[🟨🟩🟦🟪]+$", l.strip())]

    # Each valid 4-line block = 1 solved color group, extra lines = mistakes
    mistakes = max(0, len(grid_lines) - 4)

    # Get color order as list of unique colors in sequence
    color_order = []
    for line in grid_lines:
        color = line[0]
        if color not in color_order:
            color_order.append(color)

    # Assign difficulty-based point values
    # Purple hardest, then Blue, then Green, then Yellow
    base_points = {"🟪": [5, 3, 2, 1], "🟦": [3, 2, 1, 0], "🟩": [2, 1, 0, 0], "🟨": [0, 0, 0, 0]}

    points = 0
    for idx, color in enumerate(color_order):
        if color in base_points:
            # If solved earlier (lower idx), more bonus
            if idx < len(base_points[color]):
                points += base_points[color][idx]

    # Build a readable summary for the leaderboard
    summary = ""
    if mistakes == 0:
        if color_order and color_order[0] == "🟪":
            summary = "No mistakes! Solved purple first 💜"
        elif color_order and color_order[0] == "🟦":
            summary = "No mistakes! Solved blue first 💙"
        else:
            summary = "No mistake!"
    else:
        summary = f"{mistakes} mistake{'s' if mistakes != 1 else ''}"

    return mistakes, points, summary

# --- Helper to parse Strands ---
def parse_strands_result(content):
    """
    Parses NYT Strands emoji results.
    Returns (score, summary)
    """
    lines = content.splitlines()
    grid_lines = [l for l in lines if re.match(r"^[🔵💡🟡]+$", l.strip())]

    if not grid_lines:
        return 0, "No recognizable Strands result."

    # Flatten all emojis into a sequence
    sequence = "".join(grid_lines)

    correct_count = sequence.count("🔵")
    hints = sequence.count("💡")
    spangram_positions = [i for i, ch in enumerate(sequence) if ch == "🟡"]

    # Base points
    score = correct_count + (len(spangram_positions) * 5) - (hints * 2)

    # Spangram bonuses — earlier = higher reward
    if spangram_positions:
        first_pos = spangram_positions[0]
        total_len = len(sequence)
        if first_pos < total_len / 3:
            score += 3
        elif first_pos < (2 * total_len / 3):
            score += 1

    # Make a human-readable summary
    summary = f"{correct_count} correct, {hints} hint{'s' if hints != 1 else ''}"
    if spangram_positions:
        if spangram_positions[0] < len(sequence) / 3:
            summary += ", spangram early 🟡"
        elif spangram_positions[0] < (2 * len(sequence) / 3):
            summary += ", spangram mid 🟡"
        else:
            summary += ", spangram late 🟡"

    return score, summary

# --- Helper to parse Globle ---
def parse_globle_result(content):
    """
    Returns (guesses, summary)
    """
    lines = content.splitlines()

    # Find the line with the green square 🟩 — it contains the final guess count
    guess_line = next((l for l in lines if "🟩" in l), None)
    if not guess_line:
        return None, "No recognizable Globle result."

    # Extract the number after the final 🟩
    match = re.search(r"🟩\s*=\s*(\d+)", guess_line)
    if not match:
        return None, "Could not find number of guesses."

    guesses = int(match.group(1))

    # Generate a summary string based on performance
    if guesses <= 2:
        summary = f"{guesses} guesses, AMAZING 🌍"
    elif guesses <= 4:
        summary = f"{guesses} guesses, great job! 🌎"
    elif guesses <= 6:
        summary = f"{guesses} guesses, nice! 🌏"
    else:
        summary = f"{guesses} guesses"

    return guesses, summary


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip()
    username = message.author.display_name
    today = date.today().isoformat()

    # --- WORDLE ---
    if content.startswith("Wordle"):
        try:
            first_line = content.splitlines()[0]
            parts = first_line.split()
            if len(parts) >= 3 and "/" in parts[2]:
                score = int(parts[2].split("/")[0])
                if today not in daily_scores["wordle"]:
                    daily_scores["wordle"][today] = {}
                daily_scores["wordle"][today][username] = score

        except Exception as e:
            print("Error parsing Wordle:", e)

    # --- CONNECTIONS ---
    elif content.lower().startswith("connections"):
        try:
            mistakes, points, summary = parse_connections_result(content)
            if today not in daily_scores["connections"]:
                daily_scores["connections"][today] = {}
            daily_scores["connections"][today][username] = {
                "mistakes": mistakes,
                "points": points,
                "summary": summary,
            }

        except Exception as e:
            print("Error parsing Connections result:", e)


            # --- STRANDS ---
    elif content.lower().startswith("strands"):
        try:
            score, summary = parse_strands_result(content)
            today = date.today().isoformat()
            username = message.author.display_name

            if today not in daily_scores["strands"]:
                daily_scores["strands"][today] = {}

            daily_scores["strands"][today][username] = {
                "score": score,
                "summary": summary,
            }

        except Exception as e:
            print("Error parsing Strands result:", e)

    # --- GLOBLE ---
    elif "🌎" in content or "🌍" in content or "🌏" in content:
        try:
            guesses, summary = parse_globle_result(content)
            if guesses is None:
                return  # Not a valid result line

            today = date.today().isoformat()
            username = message.author.display_name

            if today not in daily_scores.get("globle", {}):
                daily_scores.setdefault("globle", {})[today] = {}

            daily_scores["globle"][today][username] = {
                "guesses": guesses,
                "summary": summary,
            }

            # await message.channel.send(
            #     f"🌎 Got your Globle result, {username}! {summary}"
            # )
        except Exception as e:
            print("Error parsing Globle result:", e)


    await bot.process_commands(message)


# @bot.command()
# async def leaderboard(ctx):
#     today = date.today().isoformat()

#     wordle_data = daily_scores["wordle"].get(today, {})
#     connections_data = daily_scores["connections"].get(today, {})
#     strands_data = daily_scores["strands"].get(today, {})
#     globle_data = daily_scores["globle"].get(today, {})

#     if not wordle_data and not connections_data and not strands_data:
#         await ctx.send("📊 No puzzle results submitted yet today.")
#         return

#     msg_lines = [f"🏆 **Daily Leaderboard — {today}**"]

#     # --- WORDLE ---
#     if wordle_data:
#         sorted_wordle = sorted(wordle_data.items(), key=lambda x: x[1])
#         msg_lines.append("\n**Wordle Rankings**")
#         for i, (name, score) in enumerate(sorted_wordle, start=1):
#             msg_lines.append(f"{i}. {name} — {score}/6")
#     else:
#         msg_lines.append("\nNo Wordle scores today.")

#     # --- CONNECTIONS ---
#     if connections_data:
#         sorted_conn = sorted(
#             connections_data.items(),
#             key=lambda x: (x[1]["mistakes"], -x[1]["points"])
#         )
#         msg_lines.append("\n**Connections Rankings**")
#         for i, (name, data) in enumerate(sorted_conn, start=1):
#             msg_lines.append(f"{i}. {name} — {data['summary']}")
#     else:
#         msg_lines.append("\nNo Connections scores today.")

#     # --- STRANDS ---
#     if strands_data:
#         sorted_strands = sorted(strands_data.items(), key=lambda x: -x[1]["score"])
#         msg_lines.append("\n**Strands Rankings**")
#         for i, (name, data) in enumerate(sorted_strands, start=1):
#             msg_lines.append(f"{i}. {name} — {data['summary']} (+{data['score']} pts)")
#     else:
#         msg_lines.append("\nNo Strands scores today.")

#     # --- GLOBLE ---
#     if "globle" in daily_scores and today in daily_scores["globle"]:
#         globle_data = daily_scores["globle"][today]
#         sorted_globle = sorted(globle_data.items(), key=lambda x: x[1]["guesses"])
#         msg_lines.append("\n**Globle Rankings**")
#         for i, (name, data) in enumerate(sorted_globle, start=1):
#             msg_lines.append(f"{i}. {name} — {data['summary']}")
#     else:
#         msg_lines.append("\nNo Globle scores today.")


#     await ctx.send("\n".join(msg_lines))




import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler

SAVE_FILE = "scores.json"

# --- Load / Save JSON ---
def load_scores():
    try:
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "wordle": {},
            "connections": {},
            "strands": {},
            "globle": {},
        }

def save_scores():
    with open(SAVE_FILE, "w") as f:
        json.dump(daily_scores, f, indent=2)

# Load any saved data on startup
daily_scores = load_scores()

# --- Modified event to always save on new messages ---
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip()
    username = message.author.display_name
    today = date.today().isoformat()

    updated = False  # track if we need to save

    # --- WORDLE ---
    if content.startswith("Wordle"):
        try:
            first_line = content.splitlines()[0]
            parts = first_line.split()
            if len(parts) >= 3 and "/" in parts[2]:
                score = int(parts[2].split("/")[0])
                daily_scores["wordle"].setdefault(today, {})[username] = score
                updated = True
        except Exception as e:
            print("Error parsing Wordle:", e)

    # --- CONNECTIONS ---
    elif content.lower().startswith("connections"):
        try:
            mistakes, points, summary = parse_connections_result(content)
            daily_scores["connections"].setdefault(today, {})[username] = {
                "mistakes": mistakes,
                "points": points,
                "summary": summary,
            }
            updated = True
        except Exception as e:
            print("Error parsing Connections result:", e)

    # --- STRANDS ---
    elif content.lower().startswith("strands"):
        try:
            score, summary = parse_strands_result(content)
            daily_scores["strands"].setdefault(today, {})[username] = {
                "score": score,
                "summary": summary,
            }
            updated = True
        except Exception as e:
            print("Error parsing Strands result:", e)

    # --- GLOBLE ---
    elif "🌎" in content or "🌍" in content or "🌏" in content:
        try:
            guesses, summary = parse_globle_result(content)
            if guesses is not None:
                daily_scores["globle"].setdefault(today, {})[username] = {
                    "guesses": guesses,
                    "summary": summary,
                }
                updated = True
        except Exception as e:
            print("Error parsing Globle result:", e)

    if updated:
        save_scores()

    await bot.process_commands(message)

import random

def build_leaderboard_text():
    today = date.today().isoformat()

    wordle_data = daily_scores["wordle"].get(today, {})
    connections_data = daily_scores["connections"].get(today, {})
    strands_data = daily_scores["strands"].get(today, {})
    globle_data = daily_scores["globle"].get(today, {})

    msg_lines = [f"🏆 **Framily Daily Leaderboard ({today})**"]

    celebratory_emojis = ["👑", "🏆", "🥇", "🎉","🔥", "✨", "🧩", "🧠", "🎊"]  # Add more here anytime!

    # --- WORDLE ---
    if wordle_data:
        sorted_wordle = sorted(wordle_data.items(), key=lambda x: x[1])
        msg_lines.append("\n**Wordle**")
        for i, (name, score) in enumerate(sorted_wordle, start=1):
            prefix = ""
            encouragement = ""

            # Add emoji for top scorer
            if i == 1:
                prefix = random.choice(celebratory_emojis) + " "

            # Encouraging messages
            if score <= 2:
                encouragement = ", AMAZING!"
            elif score <= 3:
                encouragement = ", nice job!"

            msg_lines.append(f"{i}. {prefix}**{name}** : {score}/6{encouragement}")
    else:
        msg_lines.append("\nNo Wordle scores today.")

    # --- CONNECTIONS ---
    if connections_data:
        sorted_conn = sorted(
            connections_data.items(),
            key=lambda x: (x[1]["mistakes"], -x[1]["points"])
        )
        msg_lines.append("\n**Connections**")
        for i, (name, data) in enumerate(sorted_conn, start=1):
            prefix = ""
            summary = data["summary"]

            # Emoji for top player
            if i == 1:
                prefix = random.choice(celebratory_emojis) + " "

            msg_lines.append(f"{i}. {prefix}**{name}** : {summary}")
    else:
        msg_lines.append("\nNo Connections scores today.")

    # --- STRANDS ---
    if strands_data:
        sorted_strands = sorted(strands_data.items(), key=lambda x: -x[1]["score"])
        msg_lines.append("\n**Strands**")
        for i, (name, data) in enumerate(sorted_strands, start=1):
            prefix = ""
            if i == 1:
                prefix = random.choice(celebratory_emojis) + " "
            msg_lines.append(f"{i}. {prefix}**{name}** : {data['summary']} (+{data['score']} pts)")
    else:
        msg_lines.append("\nNo Strands scores today.")

    # --- GLOBLE ---
    if globle_data:
        sorted_globle = sorted(globle_data.items(), key=lambda x: x[1]["guesses"])
        msg_lines.append("\n**Globle**")
        for i, (name, data) in enumerate(sorted_globle, start=1):
            prefix = ""
            if i == 1:
                prefix = random.choice(celebratory_emojis) + " "
            msg_lines.append(f"{i}. {prefix}**{name}** : {data['summary']}")
    else:
        msg_lines.append("\nNo Globle scores today.")

    return "\n".join(msg_lines)


@bot.command()
async def stats(ctx, user: discord.Member = None):
    """Show personal stats for yourself or another user."""
    user = user or ctx.author
    username = user.display_name
    total_scores = []

    for game in daily_scores:
        for day, results in daily_scores[game].items():
            if username in results:
                total_scores.append((game, day, results[username]))

    if not total_scores:
        await ctx.send(f"No stats found for **{username}**.")
        return

    lines = [f"📊 **Stats for {username}**"]
    for game, day, entry in total_scores[-7:]:  # last 7 entries
        lines.append(f"{day} — {game.title()}: {entry}")
    await ctx.send("\n".join(lines))

# --- Scheduled leaderboard post ---
scheduler = AsyncIOScheduler()

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is online and ready!")
    scheduler.start()

    # Replace CHANNEL_ID with your Discord channel ID
    channel = bot.get_channel(1029409485543977102)
    if channel:
        scheduler.add_job(
            lambda: channel.send(build_leaderboard_text()),
            "cron",
            hour=5,
            minute=0,
        )
        print("⏰ Daily leaderboard scheduled for 5:00 AM.")
    else:
        print("⚠️ Could not find channel; please check your channel ID.")


@bot.command()
async def leaderboard(ctx):
    await ctx.send(build_leaderboard_text())

bot.run(TOKEN)
