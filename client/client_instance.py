from telethon import TelegramClient
from config import api_id, api_hash, session_name

client = TelegramClient(session_name, api_id, api_hash, system_version="4.16.30-vxTEST")