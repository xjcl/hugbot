# hugbot

![hugbot logo](hugbot_logo.png) A Discord bot that lets you hug people! Add it to your server [here](https://discordapp.com/api/oauth2/authorize?client_id=680141163466063960&permissions=34816&scope=bot)!

![autograph example](autographed_jan_to_hugbot.png) I can also help you give autographs!

## Demo

![demo of hugbot in action](jan_thingy.mp4.gif)

## Features

- hug victims
    - `hug @user`: hugs a person's profile picture (up to 3 @'s possible)
    - `hug me`
    - `hug someone`
    - `hug everyone`: hugs 3 random people to represent the concept of "everyone"
- format options
    - `hug @user grin` or `hug @user smile` for different base emojis
    - `hug @user square` or `hug @user circle` for the full profile picture or a round cutout
    - all variants support animated/GIF profile pictures as well!
- autographs
    - `give autograph [@user]` to sign an autograph [for user]
- cooldown to prevent spam
- uptime monitoring and hug statistics

## How to run your own copy

- **Setup**: Put your ```DISCORD_BOT_SECRET``` into ```docker-compose.yml```
- **Run**: ```sudo docker-compose up```

Alternatively, using **Docker** 🐳: ```sudo docker build -t hugbot .; sudo docker run -it --rm --env DISCORD_BOT_SECRET=yourTokenHere --name hugbot --mount type=bind,src=$PWD/log,dst=/home/log hugbot```

For advanced features (admin commands, uptime reporting), find the channel/user ids by right-clicking on them and use ```--env ID_ADMIN=... --env ID_HEARTBEAT_CHANNEL=... --env ID_UPTIME_CHANNEL=...```

## Contact

See me in [the public development server](https://discord.gg/ZmbBt2A)!
