import asyncio
import os
from telegram import Bot
from dotenv import load_dotenv

async def delete_webhook():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("❌ Error: BOT_TOKEN not found in .env file.")
        return

    bot = Bot(token=token)
    print(f"🔄 Deleting webhook for bot...")
    
    success = await bot.delete_webhook(drop_pending_updates=True)
    
    if success:
        print("✅ Webhook deleted successfully! You can now run the bot locally.")
    else:
        print("❌ Failed to delete webhook.")

if __name__ == "__main__":
    asyncio.run(delete_webhook())
