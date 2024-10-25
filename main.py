import discord
import json
import os
import requests

from discord.ext import tasks
from dotenv import load_dotenv

DOTENV_FILE = '.env'
CONFIG_FILE = 'config.json'

load_dotenv(dotenv_path=DOTENV_FILE)

bot_token = os.getenv('DISCORD_TOKEN', None)

if not bot_token:
    message = (
        "Couldn't find the `bot_token` environment variable."
        "Make sure to add it to your `.env` file like this: `DISCORD_TOKEN=value_of_your_bot_token`."
    )
    raise ValueError(message)


intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

#flag if commands have been pushed to servers
synced = 0

#load config_json file
try:
    with open(CONFIG_FILE, 'r') as f:
        config_json = json.load(f)
except Exception as e:
    config_json = {}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_json, f)

@tasks.loop(seconds=5)
async def sync_commands():
    global synced
    if synced == 0:
        await tree.sync()
        synced = 1
        print('commands synced')
 
@tasks.loop(seconds=5)
async def check_messages():
    print('Checking for updates')

    for server in config_json:
        telegram_token = config_json[server]['telegram_token']
    url = 'https://api.telegram.org/bot'+telegram_token+'/getUpdates'

    try:
        response = requests.get(url)

        if response.status_code==200:
            updates = json.loads(response.content)
            # process all updates
            # shift offset

    except requests.exceptions.RequestException as e:
        #TODO inform server about the issue
        None

#show bot setup
@tree.command(
    name = 'teleinfo',
    description = 'Shows bot setup'
)
async def teleinfo(interaction: discord.Interaction):
    discord_id = str(interaction.guild.id)
    
    if discord_id not in config_json or "telegram_token" not in config_json[discord_id]:
        await interaction.response.send_message('Telegram bot account not linked', ephemeral=True)
        return

    telegram_token = config_json[discord_id]['telegram_token']

    url='https://api.telegram.org/bot'+telegram_token+'/getMe'

    try:
        response = requests.get(url)

        if response.status_code == 200:
            # Parse the JSON string into a Python dictionary
            data = json.loads(response.content)

            username = data['result']['username']
            await interaction.response.send_message('Linked to Telegram bot account **@' + username + '**', ephemeral=True)
        else:
            await interaction.response.send_message('Issue with Telegram bot account happened (' + str(response.status_code) + ')', ephemeral=True)
    
    except Exception as e:
        await interaction.response.send_message('There was an exception: ' + str(e), ephemeral=True)


#link Telegram bot
@tree.command(
    name = 'telelink',
    description = 'Links a Telegram bot account'
)
async def telelink(interaction: discord.Interaction, telegram_token:str):
    discord_id = str(interaction.guild.id)
    
    #check if Telegram is already setup
    if discord_id in config_json and "telegram_token" in config_json[discord_id]:
        message = 'Telegram already connected. Use /telestop to remove the configuration.'
        await interaction.response.send_message(message, ephemeral=True)
        return None

    #validate token
    url='https://api.telegram.org/bot'+telegram_token+'/getMe'

    try:
        response = requests.get(url)

        if response.status_code == 200:
            if discord_id not in config_json:
                config_json[discord_id] = {}

            config_json[discord_id]['telegram_token'] = telegram_token

            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_json, f, indent=4)

            message = 'Telegram linked successfully'
            await interaction.response.send_message(message, ephemeral=True)

        elif response.status_code == 404:
            message = 'Invalid token, please provide valid Telegram token.'
            await interaction.response.send_message(message, ephemeral=True)

        else:
            print('Error:', response.status_code)

            message = 'There was an error: ' + str(response.status_code)
            await interaction.response.send_message(message, ephemeral=True)

    except requests.exceptions.RequestException as e:
    
        # Handle any network-related errors or exceptions
        message = 'There was an exception: ' + str(e)
        await interaction.response.send_message(message, ephemeral=True)

#unlink Telegram bot account
@tree.command(
    name = 'telestop',
    description = 'Removes linked Telegram bot account'
)
async def telestop(interaction: discord.Interaction):
    discord_id = str(interaction.guild.id)

    if discord_id in config_json and "telegram_token" in config_json[discord_id]:
        config_json[discord_id].pop("telegram_token")

        # Clean up if no tokens are left for this server
        if not config_json[discord_id]:
            del config_json[discord_id]

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_json, f, indent=4)

        message = 'Telegram bot account unlinked'
        await interaction.response.send_message(message, ephemeral=True)

    else:
        message = 'Telegram bot account not linked'
        await interaction.response.send_message(message, ephemeral=True)

@bot.event
async def on_ready():
    sync_commands.start()
    check_messages.start()
    print('Ready')

bot.run(bot_token)
