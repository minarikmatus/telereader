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
 

#link telegram account
@tree.command(
    name = 'telelink',
    description = 'Links a Telegram account'
)
async def telelink(interaction: discord.Interaction, telegram_token:str):

    #check if Telegram is already setup
    if "telegram_token" in config_json:
        message = 'Telegram already connected. Use /telestop to remove the configuration.'
        await interaction.response.send_message(message, ephemeral=True)
        return None


    #validate token
    url='https://api.telegram.org/bot'+telegram_token+'/getMe'

    try:
        response = requests.get(url)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            config_json['telegram_token'] = telegram_token

            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_json, f)

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

#unlink telegram account
@tree.command(
    name = 'telestop',
    description = 'Removes linked Telegram account'
)
async def telestop(interaction: discord.Interaction):
    if "telegram_token" in config_json:
        config_json.pop("telegram_token")

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_json, f)

        message = 'Telegram account unlinked'
        await interaction.response.send_message(message, ephemeral=True)

    else:
        message = 'Telegram account not linked'
        await interaction.response.send_message(message, ephemeral=True)



@bot.event
async def on_ready():
    sync_commands.start()
    print('Ready')

bot.run(bot_token)
