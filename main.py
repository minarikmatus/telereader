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


# move identifier of first message
def shift_offset(token:str, update_id:int) -> None:
    offset = update_id + 1
    url = 'https://api.telegram.org/bot' + token + '/getUpdates'
    #params = {'content-type': 'application/json'}
    params = {'offset':str(offset)}
    requests.get(url, params=params)
            

def parse_messages(content:bytes):
    updates = json.loads(content)

    update_id = 0
    messages = []       # output variable

    # process all updates
    for update in updates.get('result'):
        update_id = update['update_id']

        message = None

        # message from group
        if 'message' in update and update['message']['chat']['type'] == 'group':
            chat_title, discord_message = process_group_message(update['message'])
            message = {'chat_title':chat_title, 'discord_message': discord_message}
        # message from channel
        elif 'channel_post' in update:
            chat_title, discord_message = process_channel_message(update['channel_post'])
            message = {'chat_title':chat_title, 'discord_message': discord_message}

        # if nothing is extracted lopp around
        if message is None:
            continue
        else:
            messages.append(message)

    return messages, update_id


# get text from channel udpate
def process_channel_message(message:any) -> str:
    message_text = message.get('text', '')
   
    author_signature = message.get('author_signature', '')
    if author_signature:
        author_text = author_signature + ' @ '
    else:
        author_text = ''

    chat_title = message['chat'].get('title', '')

    # compose message
    discord_message = author_text + chat_title + ':\n' \
        + '>>> ' + message_text
    
    return chat_title, discord_message


# get text from group udpate
def process_group_message(message:any) -> str:
    message_text = message.get('text', '')
    message_caption = message.get('caption', '')
    if message_text == '' and message_caption == '':
        return None

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
    discord_message = first_name + ' ' + last_name  + ' @ ' \
        + chat_title + ':\n' \
        + '>>> ' + merged_text
    
    return chat_title, discord_message


# sync command definitions to servers
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

    # get list of servers for each token
    token_dict = {}

    
    for server_id, info in config_json.items():
        token = info['telegram_token']
        
        if token not in token_dict:
            token_dict[token] = []
        
        token_dict[token].append(server_id)

    for telegram_token in token_dict.keys():

        url = 'https://api.telegram.org/bot' + telegram_token + '/getUpdates'

        try:
            response = requests.get(url)

            if response.status_code == 200:
                messages, update_id = parse_messages(response.content)
                shift_offset(telegram_token, update_id)

        except requests.exceptions.RequestException as e:
            # TODO inform servers about the issue
            None

        # send all new messages to all subscribed servers
        for message in messages:
            for server_id in token_dict[telegram_token]:
                # if subscribed, send message
                if message['chat_title'] in config_json[server_id]['subscriptions']:
                    channel_id = config_json[server_id]['channel_id']
                    channel = bot.get_channel(channel_id)
                    await channel.send(message['discord_message'])

                # if not subscribed, store chat name to chats
                elif message['chat_title'] not in config_json[server_id]['chats']:
                    config_json[server_id]['chats'].append(message['chat_title'])
                    save_config(config_json)


# show bot setup
@tree.command(
    name = 'teleinfo',
    description = 'Show bot setup'
)
async def teleinfo(interaction: discord.Interaction):
    discord_id = str(interaction.guild.id)

    if discord_id not in config_json or "telegram_token" not in config_json[discord_id]:
        await interaction.response.send_message('Telegram bot account not linked', ephemeral=True)
        return

    server_data = config_json[discord_id]
    telegram_token = server_data['telegram_token']

    channel_mention = bot.get_channel(server_data['channel_id']).mention
    channel_text = 'Posting messages to channel ' + channel_mention
    url = 'https://api.telegram.org/bot' + telegram_token + '/getMe'
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


# store updated configutation to local storage
def save_config(config_json):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_json, f, indent=4)


# link Telegram bot
@tree.command(
    name = 'telelink',
    description = 'Link a Telegram bot account'
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
        message = 'Telegram bot already connected. Use /telestop to remove the configuration.'
        await interaction.response.send_message(message, ephemeral=True)
        return None

    # validate token
    url = 'https://api.telegram.org/bot' + telegram_token + '/getMe'

    try:
        response = requests.get(url)

        if response.status_code == 200:
            if discord_id not in config_json:
                config_json[discord_id] = {}

            # save updated configuration
            config_json[discord_id]['telegram_token'] = telegram_token
            config_json[discord_id]['channel_id'] = channel.id
            config_json[discord_id]['chats'] = []
            config_json[discord_id]['subscriptions'] = []

            save_config(config_json)

            message = 'Telegram bot linked successfully'
            await interaction.response.send_message(message, ephemeral=True)

            # flush outstanding updates to prevent message flooding
            url = 'https://api.telegram.org/bot' + telegram_token + '/getUpdates'
            response_flush = requests.get(url)

            if response_flush.status_code == 200:
                messages_flush, update_id = parse_messages(response_flush.content)
                shift_offset(telegram_token, update_id)
            else:
                message = 'Could not flush previous messages'

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


# list available chats
@tree.command(
    name = 'telelist',
    description = 'List available Telegram chats'
)
async def telelist(interaction: discord.Interaction):
    discord_id = str(interaction.guild.id)

    if discord_id not in config_json:
        message = 'Telegram bot account not linked'
        await interaction.response.send_message(message, ephemeral=True)
        return

    # split chats to subscribed and available
    subscribed = ''
    available = ''
    for chat in config_json[discord_id]['chats']:
        if chat in config_json[discord_id]['subscriptions']:
            subscribed += chat + '\n'
        else:
            available += chat + '\n'

    if subscribed == '':
        subscribed_text = 'No subscribed chats'
    else:
        subscribed_text = 'Subscribed chats:\n```' + subscribed + '```'

    if available == '':
        available_text = 'No available chats'
    else:
        available_text = 'Available chats:\n```' + available + '```'

    message = subscribed_text + '\n' + available_text + '\n' \
        'To change status use /telesub `chat_title`'
    
    await interaction.response.send_message(message, ephemeral=True)


# change subscription to a chat
@tree.command(
    name = 'telesub',
    description = 'Subscribe to or unsubscribe from a Telegram chat'
)
async def telesub(interaction: discord.Interaction, chat_title:str):
    discord_id = str(interaction.guild.id)

    if discord_id not in config_json:
        message = 'Telegram bot account not linked'
        await interaction.response.send_message(message, ephemeral=True)
        return
    
    if chat_title in config_json[discord_id]['chats']:
        if chat_title in config_json[discord_id]['subscriptions']:
            config_json[discord_id]['subscriptions'].remove(chat_title)
            message = 'Unsubscribed from ' + chat_title

        else:
            config_json[discord_id]['subscriptions'].append(chat_title)
            message = 'Subscribed to `' + chat_title + '`'

        save_config(config_json)

    # chat not in the lists
    else:
        message = 'Unknown chat'
    
    await interaction.response.send_message(message, ephemeral=True)


# unlink Telegram bot account
@tree.command(
    name = 'telestop',
    description = 'Remove linked Telegram bot account'
)
async def telestop(interaction: discord.Interaction):
    discord_id = str(interaction.guild.id)

    if discord_id in config_json:
        del config_json[discord_id]
        save_config(config_json)

        message = 'Telegram bot account unlinked'

    else:
        message = 'Telegram bot account not linked'
    
    await interaction.response.send_message(message, ephemeral=True)


@bot.event
async def on_ready():
    sync_commands.start()
    check_messages.start()
    print('Ready')

bot.run(bot_token)
