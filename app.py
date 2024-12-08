import discord
import aiohttp
import sqlite3
from discord.ext import commands
from discord import app_commands

DB_PATH = "powerdns_users.db"
API_BASE_URL = "http://api.thedev.ovh:8081/api/v1/"
API_KEY = "OG9UZHhCZ1ZoV1hHSVFM"
DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"  # Replace with your bot token

class PowerDNSBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                pdns_username TEXT NOT NULL,
                pdns_account TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @app_commands.command(
        name="createaccount",
        description="Create a PowerDNS Admin user and account linked to your Discord account."
    )
    async def create_account(self, interaction: discord.Interaction):
        discord_id = interaction.user.id
        discord_username = interaction.user.name

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT pdns_username FROM users WHERE discord_id = ?", (discord_id,))
        if cursor.fetchone():
            conn.close()
            await interaction.response.send_message(
                "You already have a PowerDNS Admin account linked to your Discord account.",
                ephemeral=True
            )
            return

        pdns_username = discord_username
        pdns_password = "GeneratedSecurePassword123"
        pdns_account = discord_username

        try:
            async with aiohttp.ClientSession() as session:
                user_payload = {
                    "username": pdns_username,
                    "password": pdns_password,
                    "email": f"{discord_username}@example.com",
                    "role": "user"
                }
                async with session.post(
                    f"{API_BASE_URL}/users",
                    headers={"X-API-Key": API_KEY},
                    json=user_payload
                ) as response_user:
                    if response_user.status != 201:
                        error_msg = await response_user.text()
                        await interaction.response.send_message(
                            f"Failed to create user: {error_msg}",
                            ephemeral=True
                        )
                        conn.close()
                        return

                account_payload = {
                    "name": pdns_account,
                    "description": f"Account for {pdns_username}"
                }
                async with session.post(
                    f"{API_BASE_URL}/accounts",
                    headers={"X-API-Key": API_KEY},
                    json=account_payload
                ) as response_account:
                    if response_account.status != 201:
                        error_msg = await response_account.text()
                        await interaction.response.send_message(
                            f"Failed to create account: {error_msg}",
                            ephemeral=True
                        )
                        conn.close()
                        return

            cursor.execute(
                "INSERT INTO users (discord_id, pdns_username, pdns_account) VALUES (?, ?, ?)",
                (discord_id, pdns_username, pdns_account)
            )
            conn.commit()
            conn.close()

            try:
                await interaction.user.send(
                    f"Your PowerDNS Admin account has been created:\n"
                    f"Username: {pdns_username}\n"
                    f"Password: {pdns_password}\n"
                    f"Account Name: {pdns_account}\n"
                    f"Login at: {API_BASE_URL.replace('/api', '')}"
                )
                await interaction.response.send_message(
                    "Your PowerDNS Admin account has been created. Check your Direct Messages for login details.",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Your account has been created, but I couldn't send you a Direct Message with the details. "
                    "Please ensure your DMs are enabled and contact an administrator.",
                    ephemeral=True
                )
        except aiohttp.ClientError as e:
            conn.close()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(
        name="addrecord",
        description="Add a DNS record to your linked PowerDNS Admin account."
    )
    async def add_record(self, interaction: discord.Interaction, record: str, account_name: str):
        discord_id = interaction.user.id

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT pdns_account FROM users WHERE discord_id = ? AND pdns_account = ?",
            (discord_id, account_name)
        )
        if not cursor.fetchone():
            conn.close()
            await interaction.response.send_message(
                f"You do not have access to account `{account_name}`.",
                ephemeral=True
            )
            return

        record_type, record_content = record.split(" ", 1)
        try:
            async with aiohttp.ClientSession() as session:
                record_payload = {
                    "type": record_type.upper(),
                    "name": account_name,
                    "content": record_content,
                    "ttl": 3600
                }
                async with session.post(
                    f"{API_BASE_URL}/zones/{account_name}/records",
                    headers={"X-API-Key": API_KEY},
                    json=record_payload
                ) as response:
                    if response.status == 201:
                        await interaction.response.send_message(
                            f"Record `{record}` has been added to account `{account_name}`.",
                            ephemeral=True
                        )
                    else:
                        error_msg = await response.text()
                        await interaction.response.send_message(
                            f"Failed to add record: {error_msg}",
                            ephemeral=True
                        )
        except aiohttp.ClientError as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PowerDNSBot(bot))

# Create the bot and run it
intents = discord.Intents.default()  
intents.messages = True
intents.guilds = True
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is logged in as {bot.user}")

bot.run(DISCORD_TOKEN)  # Running the bot with the provided token