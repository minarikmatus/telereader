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

# flag if commands have been pushed to servers
synced = 0

# load config_json file
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

# check for updates and post
@tasks.loop(seconds=10)
async def check_messages():

    for server in config_json:
        server_data = config_json[server]
        telegram_token = server_data['telegram_token']

        target_channel_id = server_data['channel_id']

        url = 'https://api.telegram.org/bot' + telegram_token + '/getUpdates'

        try:
            response = requests.get(url)

            if response.status_code == 200:
                updates = json.loads(response.content)

            update_id = 0

            # process all updates
            for update in updates['result']:
                update_id = update['update_id']

                if 'message' in update:
                    message = update['message']

                    # only process messages from groups
                    if message['chat']['type'] != 'group':
                        continue

                    message_text = message.get('text', '')
                    message_caption = message.get('caption', '')
                    if message_text == '' and message_caption == '':
                        continue

                    # merge caption and text
                    merged_text = ''
                    if message_caption != '':
                        merged_text =  '<image>\n' + message_caption + '\n'
                    if message_text != '':
                        merged_text += message_text
                    if merged_text[-1] == '\n':
                        merged_text = merged_text[:-1]

                    first_name = message['from'].get('first_name', '')
                    last_name = message['from'].get('last_name', '')
                    chat_title = message['chat'].get('title', '')

                    # compose message
                    discord_message = first_name + ' ' + last_name \
                        + ' @ ' + chat_title + ':\n' \
                        + '>>> ' + merged_text
                    
                    channel = bot.get_channel(target_channel_id)
                    await channel.send(discord_message)

            # shift offset
            offset = update_id + 1
            url = 'https://api.telegram.org/bot' + telegram_token + '/getUpdates'
            params = {'content-type': 'application/json'}
            data = {'offset': str(offset) }
            response = requests.get(url, params=params, data = data)
            
        except requests.exceptions.RequestException as e:
            # TODO inform server about the issue
            
            None

# show bot setup
@tree.command(
    name = 'teleinfo',
    description = 'Shows bot setup'
)
async def teleinfo(interaction: discord.Interaction):
    discord_id = str(interaction.guild.id)
    server_data = config_json[discord_id]

    if discord_id not in config_json or "telegram_token" not in server_data:
        await interaction.response.send_message('Telegram bot account not linked', ephemeral=True)
        return

    telegram_token = server_data['telegram_token']

    channel_mention = bot.get_channel(server_data['channel_id']).mention
    channel_text = 'Posting messages to channel ' + channel_mention
    url='https://api.telegram.org/bot' + telegram_token + '/getMe'
    try:
        response = requests.get(url)

        if response.status_code == 200:
            # Parse the JSON string into a Python dictionary
            data = json.loads(response.content)

            username = data['result']['username']
            tele_text = 'Linked to Telegram bot account **@' + username + '**'
        else:
            tele_text = 'Issue with Telegram bot account happened (' + str(response.status_code) + ')'
        
        message = tele_text + '\n' \
            + channel_text
        await interaction.response.send_message(message, ephemeral=True)
    
    except Exception as e:
        await interaction.response.send_message('There was an exception: ' + str(e), ephemeral=True)


# link Telegram bot
@tree.command(
    name = 'telelink',
    description = 'Links a Telegram bot account'
)
async def telelink(interaction: discord.Interaction, telegram_token:str, channel:discord.TextChannel=None):
    discord_id = str(interaction.guild.id)
    
    # initialize channel
    if channel == None:
        channel = interaction.channel

    if type(channel) != discord.TextChannel:
        message = 'Failed to link, provide valid text channel'
        await interaction.response.send_message(message, ephemeral=True)

    # check if Telegram is already setup
    if discord_id in config_json and "telegram_token" in config_json[discord_id]:
        message = 'Telegram already connected. Use /telestop to remove the configuration.'
        await interaction.response.send_message(message, ephemeral=True)
        return None

    # validate token
    url='https://api.telegram.org/bot' + telegram_token + '/getMe'

    try:
        response = requests.get(url)

        if response.status_code == 200:
            if discord_id not in config_json:
                config_json[discord_id] = {}

            config_json[discord_id]['telegram_token'] = telegram_token
            config_json[discord_id]['channel_id'] = channel.id

            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_json, f, indent=4)

            message = 'Telegram linked successfully'
            await interaction.response.send_message(message, ephemeral=True)

        elif response.status_code == 404:
            message = 'Invalid token, please provide valid Telegram token.'
            await interaction.response.send_message(message, ephemeral=True)

        else:
            message = 'There was an error: ' + str(response.status_code)
            await interaction.response.send_message(message, ephemeral=True)

    except requests.exceptions.RequestException as e:
    
        # Handle any network-related errors or exceptions
        message = 'There was an exception: ' + str(e)
        await interaction.response.send_message(message, ephemeral=True)

# unlink Telegram bot account
@tree.command(
    name = 'telestop',
    description = 'Removes linked Telegram bot account'
)
async def telestop(interaction: discord.Interaction):
    discord_id = str(interaction.guild.id)

    if discord_id in config_json:
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
