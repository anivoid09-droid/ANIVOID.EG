from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config

# ===== COMMANDS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Bot is Alive!\nUse /help")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start\n/help\n/profile\n/balance"
    )

# ===== MAIN =====

def main():
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    print("🔥 BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
