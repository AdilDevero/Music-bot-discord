# =========================
# Importing libraries
# =========================
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
from collections import deque
import asyncio

# =========================
# Load environment variables
# =========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# =========================
# Song queues per guild
# =========================
SONG_QUEUES = {}

# =========================
# yt-dlp async helper
# =========================
async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

# =========================
# Discord intents
# =========================
intents = discord.Intents.default()
intents.message_content = True

# =========================
# Bot setup
# =========================
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# Bot ready event (PRESENCE FIXED ✅)
# =========================
@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Game(name="🎵 Music in TSX Community") #you can change the name of the discord activity
    )
    await bot.tree.sync()
    print(f"{bot.user} is online!")

# =========================
# Skip command
# =========================
@bot.tree.command(name="skip", description="Skips the current playing song")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped the current song.")
    else:
        await interaction.response.send_message("Nothing is playing.")

# =========================
# Pause command
# =========================
@bot.tree.command(name="pause", description="Pause the currently playing song.")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        return await interaction.response.send_message("I'm not in a voice channel.")
    if not vc.is_playing():
        return await interaction.response.send_message("Nothing is playing.")
    vc.pause()
    await interaction.response.send_message("⏸️ Playback paused.")

# =========================
# Resume command
# =========================
@bot.tree.command(name="resume", description="Resume the paused song.")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        return await interaction.response.send_message("I'm not in a voice channel.")
    if not vc.is_paused():
        return await interaction.response.send_message("Nothing is paused.")
    vc.resume()
    await interaction.response.send_message("▶️ Playback resumed.")

# =========================
# Stop command
# =========================
@bot.tree.command(name="stop", description="Stop playback and clear the queue.")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        return await interaction.response.send_message("I'm not connected.")

    guild_id = str(interaction.guild_id)
    SONG_QUEUES[guild_id] = deque()

    if vc.is_playing() or vc.is_paused():
        vc.stop()

    await vc.disconnect()
    await interaction.response.send_message("⏹️ Stopped and disconnected.")

# =========================
# Play command
# =========================
@bot.tree.command(name="play", description="Play a song or add it to queue.")
@app_commands.describe(song_query="Song name or keywords")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        return await interaction.followup.send("Join a voice channel first.")

    voice_channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client

    if vc is None:
        vc = await voice_channel.connect()
    elif vc.channel != voice_channel:
        await vc.move_to(voice_channel)

    ydl_options = {
        "format": "bestaudio[abr<=96]/bestaudio",
        "noplaylist": True,
        "quiet": True,
    }

    query = f"ytsearch1:{song_query}"
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries")

    if not tracks:
        return await interaction.followup.send("No results found.")

    track = tracks[0]
    audio_url = track["url"]
    title = track.get("title", "Unknown")

    guild_id = str(interaction.guild_id)
    if guild_id not in SONG_QUEUES:
        SONG_QUEUES[guild_id] = deque()

    SONG_QUEUES[guild_id].append((audio_url, title))

    if vc.is_playing() or vc.is_paused():
        await interaction.followup.send(f"➕ Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"🎶 Now playing: **{title}**")
        await play_next_song(vc, guild_id, interaction.channel)

# =========================
# Play next song
# =========================
async def play_next_song(vc, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -b:a 96k",
        }

        source = discord.FFmpegOpusAudio(
            audio_url,
            executable="bin\\ffmpeg\\ffmpeg.exe",  # remove if ffmpeg is in PATH
            **ffmpeg_options
        )

        def after_play(error):
            if error:
                print(error)
            asyncio.run_coroutine_threadsafe(
                play_next_song(vc, guild_id, channel),
                bot.loop
            )

        vc.play(source, after=after_play)
        await channel.send(f"🎧 Now playing: **{title}**")
    else:
        await vc.disconnect()

# =========================
# Run bot
# =========================
bot.run(TOKEN)
