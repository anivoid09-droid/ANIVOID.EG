from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
import database as db

# ===== PROFILE =====

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins = db.get_user(user.id)

    await update.message.reply_text(
        f"👤 {user.first_name}\n💰 Coins: {coins}"
    )

# ===== BALANCE =====

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    coins = db.get_user(user.id)

    await update.message.reply_text(f"💰 Balance: {coins}")

# ===== HANDLER LIST =====

def get_handlers():
    return [
        CommandHandler("profile", profile),
        CommandHandler("balance", balance),
    ]
