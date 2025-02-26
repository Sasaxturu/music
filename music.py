import re
import asyncio
import os
import aiohttp
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import MediaStream
from pytgcalls.exceptions import NoActiveGroupCall

# Masukkan API ID dan API Hash dari my.telegram.org
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
session_string = os.getenv('SESSION_STRING')

client = TelegramClient(StringSession(session_string), api_id, api_hash)
pytgcalls = PyTgCalls(client)

# Membersihkan nama file dan membatasi panjang
def clean_filename(filename, max_length=50):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename)
    return cleaned[:max_length]

# Mengunduh file dan konversi ke Opus
async def download_and_convert(api_url, chat_id, is_audio=True):
    headers = {'accept': '*/*'}
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"HTTP Error: {response.status}")
            result = await response.json()
            if result.get('status'):
                file_url = result['data']['url']
                title = clean_filename(result['data']['title'])
                ext = 'mp3' if is_audio else 'mp4'
                filename = f"{chat_id}_{title}.{ext}"

                async with session.get(file_url, headers=headers) as file_response:
                    with open(filename, 'wb') as file:
                        file.write(await file_response.read())

                opus_file = filename.replace('.mp3', '.opus').replace('.mp4', '.opus')
                proc = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-i', filename,
                    '-c:a', 'libopus', '-b:a', '320k',
                    '-f', 'opus', opus_file, '-y'
                )
                await proc.communicate()
                os.remove(filename)
                return opus_file
            else:
                raise Exception("Gagal mendapatkan file dari API.")

# Perintah streaming audio
@client.on(events.NewMessage(pattern='/streamaudio (.+)'))
async def stream_audio_handler(event):
    chat_id = event.chat_id
    youtube_url = event.pattern_match.group(1)
    await event.reply(f"🎧 Streaming audio...\n{youtube_url}")

    try:
        api_url = f"https://www.laurine.site/api/downloader/ytmp3?url={youtube_url}"
        audio_file = await download_and_convert(api_url, chat_id, is_audio=True)
        await pytgcalls.play(chat_id, MediaStream(audio_file))
        await event.reply(f"✅ Streaming audio dimulai!\n🎵 {audio_file}")
    except NoActiveGroupCall:
        await event.reply("❌ Tidak ada panggilan grup aktif!")
    except Exception as e:
        await event.reply(f"❌ Gagal streaming: {e}")

# Perintah streaming video
@client.on(events.NewMessage(pattern='/streamvideo (.+)'))
async def stream_video_handler(event):
    chat_id = event.chat_id
    youtube_url = event.pattern_match.group(1)
    await event.reply(f"📹 Streaming video...\n{youtube_url}")

    try:
        api_url = f"https://www.laurine.site/api/downloader/ytmp4?url={youtube_url}"
        video_file = await download_and_convert(api_url, chat_id, is_audio=False)
        await pytgcalls.play(chat_id, MediaStream(video_file))
        await event.reply(f"✅ Streaming video dimulai!\n🎬 {video_file}")
    except NoActiveGroupCall:
        await event.reply("❌ Tidak ada panggilan grup aktif!")
    except Exception as e:
        await event.reply(f"❌ Gagal streaming: {e}")

# Perintah menghentikan streaming
@client.on(events.NewMessage(pattern='/stop'))
async def stop_stream_handler(event):
    chat_id = event.chat_id
    try:
        await pytgcalls.leave_group_call(chat_id)
        await event.reply("⏹️ Streaming dihentikan!")
    except Exception as e:
        await event.reply(f"❌ Gagal menghentikan streaming: {str(e)}")
    finally:
        for file in os.listdir():
            if file.startswith(str(chat_id)) and file.endswith(".opus"):
                os.remove(file)

# Menjalankan bot
async def main():
    await client.start()
    await pytgcalls.start()
    print("Bot siap streaming!")
    await idle()

client.loop.run_until_complete(main())
