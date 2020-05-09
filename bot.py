'''
About this bot
    TODO


Preliminary reading:
    what_is_asyncio.txt
'''

import time
import datetime
import collections

import os
import random
import platform
import subprocess

import logging
import contextlib

import aiofiles
import aiohttp
import asyncio
import discord

import hugify


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8.8s] [%(funcName)16.16s()%(lineno)5.5s] %(message)s",
    # write to stdout AND log file
    handlers=[logging.StreamHandler(), logging.FileHandler(f'{datetime.datetime.now().isoformat()}.log')],
)
logger = logging.getLogger()

client = discord.Client()

is_production = os.environ['PRODUCTION'] == 'True'

MOZHEADER = {'User-Agent': 'Mozilla/5.0'}  # pretend not to be a bot =|

cooldown = collections.defaultdict(int)
RATE_LIMIT = 10
COOLDOWN_MINUTES = 10  # minutes of cooldown when RATE_LIMIT hit

client.hug_cnt_day = 0
client.on_ready_called = False


@client.event
async def on_ready():
    if client.on_ready_called:
        return

    client.on_ready_called = True

    g = discord.Game(['I won\'t reply!', 'Use *hug help*!'][is_production])
    await client.change_presence(activity=g)

    logger.info('-' * 20)
    logger.info(f'On  Python version {platform.python_version()}  discord.py version {discord.__version__}')
    logger.info('Environment: %s', ['Testing', 'PRODUCTION!!'][is_production])
    logger.info('My name: %s', client.user)
    logger.info('Servers served: %s', str(len(client.guilds)))
    logger.info('I\'m in!!')
    logger.info('-' * 20)

    heartbeat_channel = client.get_channel(680139339652792324)
    uptime_channel = client.get_channel(680139291208450061)
    cooldown[252145305825443840] = float('-inf')  # immunity for Jan!

    # - Periodically (daily) reset dictionary to prevent memory from growing infinitely
    # - Monitor bot uptime/outages
    while heartbeat_channel and uptime_channel:
        now = datetime.datetime.now()
        await asyncio.sleep(60 - now.second)
        await heartbeat_channel.send("I'm up!")

        if len(cooldown) >= 2:
            logger.info(f'COOLDOWN: {cooldown}')

        if now.hour == 23 and now.minute == 59:
            uptimestamps = [message.created_at.replace(microsecond=0) async for message in heartbeat_channel.history(limit=24*60+10) if message.created_at.day == now.day]
            uptime = len(uptimestamps) / (24 * 60)
            await uptime_channel.send(f'__**Uptime report for {now.isoformat()[:10]}**__:  {100*uptime:.2f}%')
            downtimes = [(earlier, later) for (earlier, later) in zip(uptimestamps[::-1], uptimestamps[-2::-1]) if abs(later - earlier) > datetime.timedelta(minutes=1, seconds=30)]
            for (earlier, later) in downtimes:
                await uptime_channel.send(f'* Went down at {earlier} for {later - earlier} :frowning:')
            if not downtimes:
                await uptime_channel.send('No downtime yay!! :hugging:')
            max_latency = max((timestamp.second, timestamp) for timestamp in uptimestamps if timestamp.second <= 58)
            await uptime_channel.send(f'Maximum latency: {max_latency[0]} seconds at {max_latency[1]}')
            await uptime_channel.send(f"```{subprocess.check_output(['uptime']).decode().strip()}```")
            await uptime_channel.send(f"```{subprocess.check_output(['df', '-h', '/']).decode().strip().splitlines()[-1]}```")
            await uptime_channel.send(f'Servers served: {len(client.guilds)}')
            await uptime_channel.send(f"Hugs (today/lifetime): {client.hug_cnt_day}/{len(open('hug_cnt_total').read())}")
            client.hug_cnt_day = 0

    logger.error(f'on_ready concluded unexpectedly. Heartbeat channel {heartbeat_channel} uptime channel {uptime_channel}')


async def cooldown_decrease(author):
    await asyncio.sleep(COOLDOWN_MINUTES*60)
    cooldown[author.id] -= 1
    if cooldown[author.id] == 0:
        del cooldown[author.id]

async def cooldown_increase(author):
    cooldown[author.id] += 1
    asyncio.ensure_future( cooldown_decrease(author) )
    return cooldown[author.id] >= RATE_LIMIT


async def send_message_production(message, msg_str):
    logger.info(f'OUT: {msg_str}')
    channel, author = message.channel, message.author
    msg_str += ('\n' + str(message.author.mention) + ', you are now rate-limited (I will ignore you for a while)') * await cooldown_increase(message.author)
    await channel.send(msg_str)

async def send_file_production(message, msg_str, filename_local, filename_online):
    logger.info(f'OUT: {msg_str}  FILE: {filename_online}')
    channel, author = message.channel, message.author
    msg_str += ('\n' + str(message.author.mention) + ', you are now rate-limited (I will ignore you for a while)') * await cooldown_increase(message.author)
    file = discord.File(filename_local, filename=filename_online)
    await channel.send(msg_str, file=file)

async def send_message_mock(message, msg_str):
    logger.info(f'OUT: {msg_str}')

async def send_file_mock(message, msg_str, filename_local, filename_online):
    logger.info(f'OUT: {msg_str}  FILE: {filename_online}')

send_message = send_message_production if is_production else send_message_mock
send_file = send_file_production if is_production else send_file_mock


def get_avatar_url_gif_or_png(person):
    '''https://stackoverflow.com/questions/54556637
    If no avatar URL is provided, discord will generate an avatar from the discriminator modulo 5
    Pick animated GIF when available and PNG otherwise
    Note that Discord sometimes returns an 128x128 image even if we request 256x256'''

    try:
        return str(person.avatar_url_as(static_format='png')).rsplit('?', 1)[0] + '?size=256'
    except:
        img_url = str(person.avatar_url).replace('webp', 'png').rsplit('?', 1)[0] + '?size=256'

        if not img_url:
            return f'https://cdn.discordapp.com/embed/avatars/{int(person.discriminator) % 5}.png'

        if person.avatar.startswith('a_'):
            return img_url.replace('png', 'gif')


async def avatar_download_asynchronous(person_list):
    '''Create #num_avatars separate download tasks'''

    async def download(person, i):

        async with aiohttp.ClientSession() as session:
            avatar_url = get_avatar_url_gif_or_png(person)
            async with session.get(avatar_url, headers=MOZHEADER) as resp:
                remote_img = await resp.read()

        avatar_file = f'hug{i}.' + avatar_url.rsplit('.', 1)[1]
        async with aiofiles.open(avatar_file, 'wb') as file:
            await file.write(remote_img)

        return avatar_file

    return await asyncio.gather(*(
        asyncio.ensure_future(download(person, i)) for i, person in enumerate(person_list)
    ))


# ------------------------------------

def only_run_if_activated(function):
    if os.environ['activate_feature_' + function.__name__] != 'True':
        return lambda *a, **b: asyncio.Future()
    return function


@only_run_if_activated
async def execute_code(message, i):
    '''run message as python code (very insecure)'''

    code = message.content[i+1:].replace('```', '').replace('python', '')
    if any(badstr in code for badstr in ['open', 'token', 'os', 'sys', 'exit', 'import', 'subprocess', '_', 'rm']):
        return await send_message(client, message, '**You are trying to hack me. Incident reported to FBI CIA**')

    try:
        with io.StringIO() as buf:
            with contextlib.redirect_stdout(buf):
                exec(code, {}, {})
            await send_message(message, buf.getvalue().replace('@', '@\u200b')[:2000])  # escape '@everyone' using zero-width space
    except Exception as e:
        await send_message(message, '**' + repr(e) + '**')


@only_run_if_activated
async def hug(message, message_lower):
    '''hug a person's profile picture'''

    if 'hug help' in message_lower:
        return await send_message(message, '''__Hi! I'm a bot who hugs people!__
            - **Huggee**: You can `hug me`, `hug @user`, `hug someone`, and `hug everyone`
            - **Crop**: You can `hug @user square` for their full avatar or `hug @user circle` for a round cutout
            - **Base**: You can `hug @user grin` or `hug @user smile` for different base emojis
            - **Autograph**: You can `give autograph [@user]` to sign an autograph [for user]
            - **Cooldown**: I will stop responding if you send too many requests
            - **Add me to your server**: <https://discordapp.com/api/oauth2/authorize?client_id=680141163466063960&permissions=34816&scope=bot>
            - **Contact**: See me in the public development server: <https://discord.gg/ZmbBt2A> :slight_smile:''')

    if 'hug attach' in message_lower or 'hug this' in message_lower:
        if not message.attachments:
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(message.attachments[0].url, headers=MOZHEADER) as resp:
                async with aiofiles.open('attach', 'wb') as file:
                    await file.write(await resp.read())

        fn = hugify.apply_gif_save(['attach'], hugify.hugged, 'hugged.gif', maxsize=180)  # 200
        return await send_file(message, '', fn, fn)

    start_time = time.time()
    str_huggees = lambda a: str([str(s) for s in a])

    hug_everyone = message.mention_everyone or 'everyone' in message_lower
    huggee_list = message.mentions + \
        [message.author                         ] * ('hug me'       in message_lower) + \
        [client.user                            ] * ('hug yourself' in message_lower) + \
        [random.choice(message.guild.members)   ] * ('hug someone'  in message_lower) + \
         message.guild.members                    * (hug_everyone)

    huggee_list = random.sample( huggee_list, len(huggee_list[:3]) )

    logger.info(f'HUG: {str_huggees(huggee_list)} {"@everyone" * hug_everyone}')

    if not huggee_list:
        return

    crop_mode = 'circle' if 'circle' in message_lower else 'square'
    base_mode = 'grin'   if 'grin'   in message_lower else 'smile'

    with message.channel.typing():

        in_filenames = await avatar_download_asynchronous(huggee_list)

        logger.info(f'Done downloading t={time.time() - start_time}')
        logger.info(f'{in_filenames}')

        reply = 'Please refrain from mentioning everyone, use "hug everyone" (no @) instead' * message.mention_everyone

        fn = hugify.apply_gif_save(in_filenames, hugify.hugged, 'hugged.gif', maxsize=180, base_mode=base_mode, crop_mode=crop_mode)
        await send_file(message, reply, fn, fn)
        # await send_file(message, reply, fn, 'hugged ' + str_huggees(huggee_list) + '.gif')

        client.hug_cnt_day += 1
        logger.info(f'Done t={time.time() - start_time}')
        logger.info(client.hug_cnt_day)
        open('hug_cnt_total', 'a').write('.')


@client.event
async def on_message(message):

    # don't respond to own messages
    if message.author == client.user:
        return

    logger.info(f'IN: [{str(message.guild): <16.16} #{str(message.channel): <16.16} {message.author.id} @{str(message.author): <18.18}]: {message.content}')

    # don't respond to bots
    if message.author.bot:
        return logger.info(f'INTERNAL: Message by bot {message.author} -> message ignored')

    # rate-limit spammers:  allow RATE_LIMIT messages per COOLDOWN_MINUTES minutes
    if cooldown.get(message.author.id, 0) >= RATE_LIMIT:
        return logger.info(f'INTERNAL: Message by {message.author} who is rate limited -> message ignored')

    message_lower = message.content.lower()
    i = message_lower.find('\n')
    if '```python' in message_lower[:i]:
        await execute_code(message, i)

    # reverse input
    if 'revers' in message_lower:
        await send_message(message, message.content[::-1].replace('@', '@​\u200b'))  # escape '@everyone' using zero-width space

    if 'good bot' == message_lower:
        await send_message(message, 'uwu')

    if 'uh' + '-' * (len(message_lower) - 2) == message_lower:
        await send_message(message, message_lower + '-')

    # hugify!! ^_^
    if message_lower.startswith('hug'):
        await hug(message, message_lower)

    if 'give autograph' in message_lower:
        in_filenames = await avatar_download_asynchronous([message.author])
        top_text = f'To: {str(message.mentions[0])[:-5]}' if message.mentions else message.content[message_lower.find('autograph')+10:]
        fn = hugify.apply_gif_save([in_filenames[0]], hugify.autographed, texts=[str(message.author)[:-5], top_text] )
        return await send_file(message, '', fn, fn)


client.run(os.environ['DISCORD_BOT_SECRET'])
