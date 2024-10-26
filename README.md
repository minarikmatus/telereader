# telereader

Discord bot to forward messages from Telegram groups or channels to Discord.

# Commands

`/teleinfo` Shows linked Telegram bot name and target channel.

`/telelink telegram_token #channel` Links this bot with Telegram bot account and sets target channel for forwarded messages. If no channel is provided, links with current channel.

`/telestop` Unlinks Telegram bot account from this bot.

# Setup for Telegram groups

1. Create Telegram bot using @BotFather
2. Enable groups for Telegram bot - to be allowed to join groups
3. Disable Telegram's bot's privacy mode for groups - to start receiving group messages
4. Add Telegram bot to relevant groups

# Setup for Telegram channels

1. Create Telegram bot using @BotFather
2. Change channel admin rights - uncheck all
3. Ask owners of relevant channels to add a bot - no admin rights required

# Discord setup

1. Add this bot to Discord server and use /telelink command
