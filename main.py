from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config
import database as db
import handlers

# ===== BASIC COMMANDS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Bot is Alive!\nUse /help")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start\n/help\n/profile\n/balance"
    )

# ===== MAIN =====

def main():
    print("🚀 Starting Bot...")

    # Initialize database
    db.init_db()

    # Create bot
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # Add custom handlers
    for h in handlers.get_handlers():
        app.add_handler(h)

    print("🔥 BOT STARTED SUCCESSFULLY")

    # Run bot
    app.run_polling()

# ===== START =====

if __name__ == "__main__":
    main()
