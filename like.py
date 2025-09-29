import logging
from datetime import datetime, time, timedelta
from typing import Dict, Tuple, Optional
import pytz
import asyncio
import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = "8297079154:AAEe_Lc8gCKdjD3jhGebhsKkcsHc0w3hDuc"

ALLOWED_GROUPS = {
    -1002834792592: {"name": "Main Group", "remain": 100, "initial_remain": 100},
    -1002590196868: {"name": "Friend Group", "remain": 50, "initial_remain": 50},
}

ADMIN_USER_IDS = {7114214481}

# API Configuration
API_URL = "http://47.84.86.76:1304/likes"
API_TIMEOUT = 120  
API_RETRIES = 3  

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BotData:
    user_daily_usage: Dict[int, Dict[int, bool]] = {}

bot_data = BotData()

async def reset_daily_limits(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset daily usage limits at 4 AM +07:00."""
    bot_data.user_daily_usage = {}
    for group_id in ALLOWED_GROUPS:
        ALLOWED_GROUPS[group_id]["remain"] = ALLOWED_GROUPS[group_id-protection]
    logger.info("Daily limits reset at 4 AM +07:00")

async def is_user_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, str]:
    """Check if user is allowed to use the command."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if chat_id not in ALLOWED_GROUPS:
        return False, "❌ This bot only works in specific groups."
    
    if user_id in ADMIN_USER_IDS:
        return True, ""
    
    if bot_data.user_daily_usage.get(chat_id, {}).get(user_id, False):
        return False, "⏳ You can only use this once per day. Try again after 4 AM."
    
    if ALLOWED_GROUPS[chat_id]["remain"] <= 0:
        return False, "🔴 No remaining uses left. Resets at 4 AM."
    
    return True, ""

async def call_like_api(region: str, uid: str) -> Optional[dict]:
    """Make API request with enhanced error handling."""
    params = {
        "uid": uid,
        "amount_of_likes": 100,
        "auth": "gaycow",
        "region": region
    }
    
    for attempt in range(API_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    API_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
                ) as response:
                    
                    if response.status != 200:
                        logger.warning(f"API returned status {response.status}")
                        continue
                        
                    data = await response.json()
                    if "message" in data and "nickname" not in data:
                        return {"error": data.get("message", "Unknown error from API")}
                    if "nickname" in data or "sent" in data:
                        return data
                    
                    logger.warning(f"API error: {data.get('message', 'Invalid response format')}")
                    return {"error": data.get("message", "Invalid response format")}
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout on attempt {attempt + 1}")
            if attempt < API_RETRIES - 1:
                await asyncio.sleep(5)
            continue
                
        except Exception as e:
            logger.error(f"API call failed: {str(e)}")
            if attempt < API_RETRIES - 1:
                await asyncio.sleep(2)
            continue
    
    return {"error": "Failed to connect to API after multiple attempts"}

async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /like and /likes commands."""
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if update.effective_chat.type == "private":
            await update.message.reply_text("🔒 This bot only works in group chats.")
            return
            
        if chat_id not in ALLOWED_GROUPS:
            await update.message.reply_text("🚫 This bot only works in authorized groups.")
            return
            
        if len(context.args) < 2:
            await update.message.reply_text("📝 Usage: /like {region} {uid}\nExample: /like vn 2437607413")
            return
            
        region, uid = context.args[0], context.args[1]
        
        allowed, reason = await is_user_allowed(update, context)
        if not allowed:
            await update.message.reply_text(reason)
            return
            
        processing_msg = await update.message.reply_text(
            f"⏳ Sending likes to UID {uid}...\n"
            f"Please wait (may take 1-2 minutes)"
        )
        
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action="typing"
        )
        
        api_data = await call_like_api(region, uid)
        
        if "error" in api_data:
            await processing_msg.edit_text(
                f"⚠️ Failed to process request: {api_data['error']}\n"
                "• Server may be busy\n"
                "• Invalid UID/region\n"
                "• Try again later"
            )
            return
            
        if user_id not in ADMIN_USER_IDS:
            if chat_id not in bot_data.user_daily_usage:
                bot_data.user_daily_usage[chat_id] = {}
            bot_data.user_daily_usage[chat_id][user_id] = True
            ALLOWED_GROUPS[chat_id]["remain"] -= 1
        
        response_lines = ["✅ Successfully sent likes!\n"]
        fields = {
            "nickname": "👤 Nickname",
            "region": "🌍 Region",
            "level": "🎮 Level",
            "exp": "🔥 Experience",
            "likes_antes": "❤️ Likes Before",
            "likes_depois": "❤️ Likes After",
            "sent": "✨ Likes Sent"
        }
        for key, label in fields.items():
            if key in api_data:
                response_lines.append(f"{label}: {api_data[key]}")
        response_lines.append("\nJoin our community: [thế giới của họ đông người quá...](https://t.me/Deverloperchat)")
        response_msg = "\n".join(response_lines)
        
        await processing_msg.edit_text(response_msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Command error: {str(e)}", exc_info=True)
        if 'processing_msg' in locals():
            await processing_msg.edit_text("⚠️ An unexpected error occurred. Please try again.")
        else:
            await update.message.reply_text("⚠️ An error occurred. Please try again.")

async def remain_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show remaining request limits."""
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if chat_id not in ALLOWED_GROUPS:
            await update.message.reply_text("❌ This bot only works in specific groups.")
            return
            
        group = ALLOWED_GROUPS[chat_id]
        now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
        
        reset_time = (now + timedelta(days=1)).replace(
            hour=4, minute=0, second=0, microsecond=0
        ) if now.hour >= 4 else now.replace(
            hour=4, minute=0, second=0, microsecond=0
        )
        
        response = (
            f"📊 Limits for {group['name']}:\n\n"
            f"🔄 Remaining: {group['remain']}/{group['initial_remain']}\n"
            f"⏰ Resets at: {reset_time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"👤 Your limit: {'∞ (Admin)' if user_id in ADMIN_USER_IDS else '1/1'}\n\n"
            f"Note: Daily reset at 4 AM"
        )
        
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Remain command error: {str(e)}")
        await update.message.reply_text("⚠️ Couldn't check limits. Please try again.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("⚠️ A system error occurred. Please try again later.")

def main() -> None:
    """Start the bot with enhanced configuration."""
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler(["like", "likes"], like_command))
    app.add_handler(CommandHandler("remain", remain_command))
    
    app.add_error_handler(error_handler)
    
    job_queue = app.job_queue
    if job_queue:
        reset_time = time(hour=21, minute=0, tzinfo=pytz.UTC)
        job_queue.run_daily(reset_daily_limits, time=reset_time)
    
    logger.info("Bot đang chạy rồi cu")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()