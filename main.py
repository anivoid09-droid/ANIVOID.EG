
```python
# bot/main.py
import logging
import asyncio
import os
import time

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project imports
import config
import database
from utils import helpers # Assuming utils.helpers exists for common utilities

# Import all handler modules
from handlers import (
    profile,
    explore,
    raid,
    cards,
    guild,
    tournament,
    economy,
    admin,
    aivra,
    moderation,
)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application: Application):
    """
    Callback function to run after the bot starts up successfully.
    Initializes the database and schedules periodic jobs.
    """
    logger.info("Bot started successfully. Performing post-initialization tasks...")
    
    # Initialize the SQLite database
    await database.initialize_db()
    logger.info("Database initialized successfully.")

    # Ensure the admin user is registered in the database
    # This is crucial for admin commands to work and for tracking the admin's existence.
    await database.add_user(config.ADMIN_ID, "AdminUser", is_admin=True)
    logger.info(f"Admin user with ID {config.ADMIN_ID} ensured in the database.")

    # Initialize and start APScheduler for scheduled tasks (e.g., ads)
    if config.AD_INTERVAL_HOURS > 0:
        scheduler = AsyncIOScheduler()
        # The send_scheduled_ads job is added to run at specified intervals.
        # It takes the bot instance as an argument to send messages.
        scheduler.add_job(
            send_scheduled_ads,
            'interval',
            hours=config.AD_INTERVAL_HOURS,
            args=(application.bot,)
        )
        scheduler.start()
        logger.info(f"Ad scheduler started. Ads will be sent every {config.AD_INTERVAL_HOURS} hours.")
    else:
        logger.warning("AD_INTERVAL_HOURS is set to 0 or less in config.py. Ad scheduling is disabled.")

async def send_scheduled_ads(bot):
    """
    Function executed by APScheduler to send advertisements to all tracked groups.
    """
    logger.info("Attempting to send scheduled advertisements.")
    
    # Retrieve all active ads and groups from the database
    ads = await database.get_all_ads()
    groups_to_advertise = await database.get_all_groups()

    if not ads:
        logger.warning("No advertisements found in the database. Skipping ad broadcast.")
        return
    if not groups_to_advertise:
        logger.warning("No groups registered for advertising. Skipping ad broadcast.")
        return

    # For demonstration, we'll pick the first available ad.
    # In a real scenario, you might want to randomize ads or cycle through them.
    ad_to_send = ads[0] 

    sent_count = 0
    for group in groups_to_advertise:
        try:
            # Send the ad, including an image if available
            if ad_to_send.image_file_id:
                await bot.send_photo(
                    chat_id=group.chat_id,
                    photo=ad_to_send.image_file_id,
                    caption=ad_to_send.text
                )
            else:
                await bot.send_message(
                    chat_id=group.chat_id,
                    text=ad_to_send.text
                )
            sent_count += 1
            # Add a small delay to avoid hitting Telegram API rate limits
            await asyncio.sleep(0.1) 
            logger.info(f"Successfully sent ad '{ad_to_send.text[:30]}...' to group {group.chat_title} ({group.chat_id}).")
        except Exception as e:
            logger.error(f"Failed to send ad to group {group.chat_title} ({group.chat_id}): {e}", exc_info=True)
            # Consider implementing logic to remove groups where the bot is no longer admin or has been kicked.

    logger.info(f"Finished scheduled ad broadcast. Sent to {sent_count}/{len(groups_to_advertise)} groups.")

async def start(update, context):
    """
    Handles the /start command. Registers the user and provides a welcome message.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Register the user in the database if they don't exist
    await database.add_user(user.id, user.username)

    if update.effective_chat.type == "private":
        await update.message.reply_text(
            f"🌟 Welcome, {user.first_name}! Your Anime RPG adventure begins now!\n"
            "Use the menu or type commands like /profile, /explore, or /raid to get started."
        )
    elif update.effective_chat.type in ["group", "supergroup"]:
        # In a group, just acknowledge and inform to use private chat for full features.
        # The `track_group_chats` handler will save the group info.
        await update.message.reply_text(
            "Hello everyone! I'm your Anime RPG Bot! 🤖\n"
            "Please use /start in a private chat with me to access all game features!"
        )

async def track_group_chats(update, context):
    """
    Automatically tracks and saves group chat IDs and titles whenever a message is received in a group.
    This ensures the bot can broadcast ads or messages to all active groups.
    """
    chat = update.effective_chat
    if chat.type in ["group", "supergroup"]:
        await database.add_group(chat.id, chat.title)
        logger.debug(f"Group chat '{chat.title}' ({chat.id}) tracked/updated.")

async def unknown_command(update, context):
    """
    Handles messages that start with '/' but do not match any registered command handlers.
    """
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            f"🤔 Sorry, I don't recognize the command '{update.message.text}'. "
            "Please check for typos or use /start to see available options."
        )
    else:
        # In groups, ignore unknown commands to avoid spam
        logger.info(f"Unknown command '{update.message.text}' received in group {update.effective_chat.title}.")


async def global_error_handler(update, context):
    """
    Centralized error handler for the bot. Logs errors and notifies the user if possible.
    """
    logger.error("An error occurred while processing an update:", exc_info=context.error)

    if update and update.effective_message:
        try:
            # Attempt to send a user-friendly error message
            await update.effective_message.reply_text(
                "💥 Oops! Something unexpected went wrong. Our magical servers are experiencing turbulence. "
                "Please try that again in a moment!"
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}", exc_info=True)
    else:
        logger.error("Error occurred, but no effective message to reply to.", exc_info=True)


def main():
    """
    Main function to initialize and run the Telegram bot.
    """
    # Validate BOT_TOKEN from config
    if not config.BOT_TOKEN or config.BOT_TOKEN == "8650797200:AAFSjsu_2BqshqH8Y6JIYs2HJh3sbdMfmMI":
        logger.error("🚫 TELEGRAM_BOT_TOKEN is not set or is a placeholder in config.py or .env file!")
        raise ValueError("BOT_TOKEN is missing or invalid. Please set it in your .env file or config.py.")

    # Build the Application instance for the bot
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init) # Register post_init for async startup tasks
        .build()
    )

    # Register global error handler first
    application.add_error_handler(global_error_handler)

    # --- Handler Registration with Priority Groups ---
    # Handlers are processed in increasing order of their 'group' number.
    # Lower group numbers mean higher priority (processed earlier).

    # Group 0: Core game commands (e.g., profile, explore, raid, etc.)
    # These are specific commands that should generally be processed before more generic handlers.
    profile.register_handlers(application, group=0)
    explore.register_handlers(application, group=0)
    raid.register_handlers(application, group=0)
    cards.register_handlers(application, group=0)
    guild.register_handlers(application, group=0)
    tournament.register_handlers(application, group=0)
    economy.register_handlers(application, group=0)

    # Group 1: General interaction commands and group tracking
    # /start command is fundamental. Group tracker ensures bot remembers where it is.
    application.add_handler(CommandHandler("start", start), group=1)
    # Message handler to automatically track new groups and update existing ones.
    # Filters ensure it only runs for group messages that are not commands.
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, track_group_chats),
        group=1,
    )

    # Group 5: Moderation handlers
    # These might involve reacting to specific keywords or patterns in general messages.
    # They should run after basic commands but before more general AI/admin text processing.
    moderation.register_handlers(application, group=5)

    # Group 10: Admin handlers
    # Specific admin commands (e.g., /admins, /broadcast) are usually handled by group 0 or similar.
    # This group is for admin-specific *message* handlers, e.g., for reply-based configurations.
    admin.register_handlers(application, group=10)

    # Group 20: AIVRA (AI) handler
    # This acts as a general text processor if no specific command or higher-priority text handler matches.
    # This fulfills the "AI last" requirement for general text.
    aivra.register_handlers(application, group=20)

    # Group 100: Unknown command handler (Lowest priority)
    # This catches any message that starts with '/' but wasn't handled by any CommandHandler in higher priority groups.
    application.add_handler(
        MessageHandler(filters.COMMAND, unknown_command), group=100
    )
    # Note: General unhandled text messages (not starting with '/') will fall through to the AIVRA handler (group 20).

    logger.info("Bot setup complete. Starting polling for updates...")
    # Start the bot in polling mode
    application.run_polling()


if __name__ == "__main__":
    main()

```

```python
# bot/config.py
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# --- Telegram Bot Configuration ---
# Your bot's unique token obtained from BotFather.
# It's recommended to store this in an environment variable for security.
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8650797200:AAFSjsu_2BqshqH8Y6JIYs2HJh3sbdMfmMI")

# The Telegram User ID of the bot administrator.
# This user will have access to admin-only commands and panels.
ADMIN_ID = int(os.getenv("ADMIN_ID", "7036768966")) # Replace with your actual admin user ID

# --- Database Configuration ---
# The name/path for the SQLite database file.
DB_NAME = "data/database.db"

# --- APScheduler Configuration ---
# Interval (in hours) at which the bot will send scheduled advertisements to groups.
# Set to 0 or a negative value to disable scheduled ads.
AD_INTERVAL_HOURS = int(os.getenv("AD_INTERVAL_HOURS", "7")) # Example: Every 7 hours

# --- Game Constants ---
# Example: Cost to create a guild
GUILD_CREATION_COST = int(os.getenv("GUILD_CREATION_COST", "200000"))
# Example: Maximum members a guild can have
MAX_GUILD_MEMBERS = int(os.getenv("MAX_GUILD_MEMBERS", "50"))
# Example: Base time (in seconds) a character is dead after defeat
CHARACTER_DEAD_DURATION_SECONDS = int(os.getenv("CHARACTER_DEAD_DURATION_SECONDS", "10800")) # 3 hours
# Example: Reward for winning a card fight
CARD_FIGHT_WIN_REWARD = int(os.getenv("CARD_FIGHT_WIN_REWARD", "10000"))
# Example: Max players in a tournament
MAX_TOURNAMENT_PLAYERS = int(os.getenv("MAX_TOURNAMENT_PLAYERS", "16"))

# --- Chat IDs for any required force-join or specific channels (if applicable) ---
# This structure is carried over from the previous Anime Forward Bot,
# but might not be directly used in the RPG bot unless a similar system is implemented.
REQUIRED_CHATS = [
    # {"id": -100..., "link": "https://t.me/...", "name": "Group 1"},
    # {"id": -100..., "link": "https://t.me/...", "name": "Group 2"},
    # {"id": -100..., "link": "https://t.me/...", "name": "Channel"},
]

```

```python
# bot/database.py
import aiosqlite
import logging
import time
import os
from config import DB_NAME # Ensure DB_NAME is defined in config.py

logger = logging.getLogger(__name__)

# --- Data Transfer Objects (DTOs) for better type hinting and readability ---
class User:
    def __init__(self, user_id, username, coins=0, bank=0, xp=0, level=1, rank='Bronze', is_dead=False, dead_until=0.0, selected_character_id=None):
        self.user_id = user_id
        self.username = username
        self.coins = coins
        self.bank = bank
        self.xp = xp
        self.level = level
        self.rank = rank
        self.is_dead = is_dead
        self.dead_until = dead_until
        self.selected_character_id = selected_character_id

class Ad:
    def __init__(self, ad_id, text, image_file_id, created_by):
        self.ad_id = ad_id
        self.text = text
        self.image_file_id = image_file_id
        self.created_by = created_by

class Group:
    def __init__(self, chat_id, chat_title, last_ad_time=0.0):
        self.chat_id = chat_id
        self.chat_title = chat_title
        self.last_ad_time = last_ad_time

# --- Database Helper Functions ---
async def _execute_query(query, params=(), fetchone=False, fetchall=False):
    """
    Internal helper to execute SQL queries. Handles connection and basic error logging.
    """
    try:
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            if fetchone:
                return await cursor.fetchone()
            if fetchall:
                return await cursor.fetchall()
            return cursor.lastrowid # Useful for getting the ID of a newly inserted row
    except aiosqlite.Error as e:
        logger.error(f"Database error executing query: {query} with params {params}. Error: {e}", exc_info=True)
        return None

async def initialize_db():
    """
    Initializes the SQLite database. Creates all necessary tables if they don't already exist.
    """
    logger.info("Checking/creating database tables...")
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 0,
            bank INTEGER DEFAULT 0,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            rank TEXT DEFAULT 'Bronze',
            is_dead BOOLEAN DEFAULT FALSE,
            dead_until REAL DEFAULT 0.0,
            selected_character_id INTEGER,
            FOREIGN KEY (selected_character_id) REFERENCES characters (char_id)
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS characters (
            char_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            power INTEGER NOT NULL,
            skill TEXT,
            image_file_id TEXT,
            description TEXT,
            rarity TEXT
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS cards (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            power INTEGER NOT NULL,
            skill TEXT,
            image_file_id TEXT,
            description TEXT,
            rarity TEXT
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS maps (
            map_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            boss_count INTEGER NOT NULL,
            danger_level INTEGER NOT NULL,
            reward_multiplier REAL NOT NULL,
            image_file_id TEXT
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS bosses (
            boss_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            power INTEGER NOT NULL,
            health INTEGER NOT NULL,
            description TEXT,
            image_file_id TEXT,
            type TEXT -- e.g., 'explore_boss', 'raid_boss', 'guild_boss'
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            leader_id INTEGER NOT NULL,
            guild_points INTEGER DEFAULT 0,
            creation_time REAL,
            FOREIGN KEY (leader_id) REFERENCES users (user_id)
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS guild_members (
            guild_id INTEGER,
            user_id INTEGER,
            join_time REAL,
            role TEXT, -- e.g., 'Member', 'Leader'
            PRIMARY KEY (guild_id, user_id),
            FOREIGN KEY (guild_id) REFERENCES guilds (guild_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS tournaments (
            tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT, -- e.g., 'Open', 'Ongoing', 'Finished'
            start_time REAL,
            end_time REAL,
            winner_id INTEGER,
            reward_coins INTEGER,
            reward_xp INTEGER,
            reward_item_type TEXT, -- e.g., 'character', 'card'
            reward_item_id INTEGER,
            FOREIGN KEY (winner_id) REFERENCES users (user_id)
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS tournament_participants (
            tournament_id INTEGER,
            user_id INTEGER,
            character_id INTEGER,
            PRIMARY KEY (tournament_id, user_id),
            FOREIGN KEY (tournament_id) REFERENCES tournaments (tournament_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (character_id) REFERENCES characters (char_id)
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS ads (
            ad_id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            image_file_id TEXT,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (user_id)
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS groups_to_advertise ( -- Renamed from 'groups' to avoid Python keyword conflict
            chat_id INTEGER PRIMARY KEY,
            chat_title TEXT,
            last_ad_time REAL DEFAULT 0.0
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS user_characters (
            user_id INTEGER,
            char_id INTEGER,
            current_health INTEGER DEFAULT 100,
            status TEXT DEFAULT 'Alive', -- e.g., 'Alive', 'Dead'
            dead_until REAL DEFAULT 0.0,
            PRIMARY KEY (user_id, char_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (char_id) REFERENCES characters (char_id)
        )
    """)
    await _execute_query("""
        CREATE TABLE IF NOT EXISTS user_cards (
            user_id INTEGER,
            card_id INTEGER,
            PRIMARY KEY (user_id, card_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (card_id) REFERENCES cards (card_id)
        )
    """)
    logger.info("All database tables checked/created successfully.")


# --- User Management ---
async def add_user(user_id: int, username: str, is_admin: bool = False):
    """
    Adds a new user to the database if they don't exist, or updates their username.
    Initializes new users with default game stats.
    """
    current_time = time.time()
    # Insert or ignore ensures that if the user_id already exists, no new row is created.
    # The username is then updated separately in case it changed.
    query = """
        INSERT OR IGNORE INTO users (user_id, username, is_dead, dead_until)
        VALUES (?, ?, ?, ?)
    """
    # Default is_dead to FALSE, dead_until to 0.0
    await _execute_query(query, (user_id, username, False, 0.0))

    # Always update the username, as it can change on Telegram
    update_query = "UPDATE users SET username = ? WHERE user_id = ?"
    await _execute_query(update_query, (username, user_id))
    logger.debug(f"User {username} ({user_id}) ensured in database.")

    # You could also set a specific 'admin' status if that's a column in users table
    # For now, ADMIN_ID from config is used to check admin status.

async def get_user(user_id: int) -> User | None:
    """Fetches a user's data from the database."""
    row = await _execute_query("SELECT user_id, username, coins, bank, xp, level, rank, is_dead, dead_until, selected_character_id FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if row:
        return User(*row)
    return None

async def is_user_dead(user_id: int) -> bool:
    """
    Checks if the user's currently selected character is dead and has not revived yet.
    """
    # Assuming `selected_character_id` in the `users` table indicates the active character.
    # And `user_characters` table tracks individual character's status.
    query = """
        SELECT uc.status, uc.dead_until FROM user_characters uc
        JOIN users u ON u.user_id = uc.user_id
        WHERE u.user_id = ? AND uc.char_id = u.selected_character_id
    """
    result = await _execute_query(query, (user_id,), fetchone=True)
    if result and result[0] == 'Dead' and result[1] > time.time():
        return True
    return False

async def get_dead_until_timestamp(user_id: int) -> float:
    """
    Retrieves the timestamp when the user's selected character will revive.
    Returns 0.0 if not found or not dead.
    """
    query = """
        SELECT uc.dead_until FROM user_characters uc
        JOIN users u ON u.user_id = uc.user_id
        WHERE u.user_id = ? AND uc.char_id = u.selected_character_id
    """
    result = await _execute_query(query, (user_id,), fetchone=True)
    if result:
        return result[0]
    return 0.0

# --- Group Management for Ads ---
async def add_group(chat_id: int, chat_title: str):
    """
    Adds a new group to the `groups_to_advertise` table or updates its title if it already exists.
    This helps the bot keep track of all groups it's a part of for broadcasting.
    """
    query = """
        INSERT OR REPLACE INTO groups_to_advertise (chat_id, chat_title)
        VALUES (?, ?)
    """
    await _execute_query(query, (chat_id, chat_title))
    logger.debug(f"Group '{chat_title}' ({chat_id}) saved/updated in groups_to_advertise table.")

async def get_all_groups() -> list[Group]:
    """Retrieves all groups registered for advertisement."""
    rows = await _execute_query("SELECT chat_id, chat_title, last_ad_time FROM groups_to_advertise", fetchall=True)
    return [Group(*row) for row in rows] if rows else []

# --- Ad Management ---
async def get_all_ads() -> list[Ad]:
    """Retrieves all stored ads for scheduled broadcasting."""
    rows = await _execute_query("SELECT ad_id, text, image_file_id, created_by FROM ads", fetchall=True)
    return [Ad(*row) for row in rows] if rows else []

# --- Placeholder for other DB operations for game features (e.g., add_character, get_map, etc.) ---
# These functions would be implemented as the game features are built out in their respective handler files.

```

```python
# bot/requirements.txt
python-telegram-bot==20.7
apscheduler
aiosqlite
python-dotenv
```

```python
# bot/.env
TELEGRAM_BOT_TOKEN=8650797200:AAFSjsu_2BqshqH8Y6JIYs2HJh3sbdMfmMI
ADMIN_ID=7036768966
AD_INTERVAL_HOURS=7
GUILD_CREATION_COST=200000
MAX_GUILD_MEMBERS=50
CHARACTER_DEAD_DURATION_SECONDS=10800
CARD_FIGHT_WIN_REWARD=10000
MAX_TOURNAMENT_PLAYERS=16
```

```python
# bot/Procfile
worker: python main.py
```

```json
{
  "deploy": {
    "startCommand": "python main.py"
  }
}
```
