'''
About this bot
    TODO


Preliminary reading:
    what_is_asyncio.txt
'''

import time
import datetime
import collections

import io
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
from discord.ext import tasks

import hugify


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8.8s] [%(funcName)16.16s()%(lineno)5.5s] %(message)s",
    # write to stdout AND log file
    handlers=[logging.StreamHandler(), logging.FileHandler(f'log/hugbot_{datetime.datetime.now().isoformat()}.log')],
)
logger = logging.getLogger()

client = discord.Client()
client.hug_cnt_day = 0

MOZHEADER = {'User-Agent': 'Mozilla/5.0'}  # pretend not to be a bot =|

cooldown = collections.defaultdict(int)
RATE_LIMIT = 10
COOLDOWN_MINUTES = 10  # minutes of cooldown when RATE_LIMIT hit

is_production = os.environ['PRODUCTION'] == 'True'
id_admin = int(os.environ.get('ID_ADMIN', 0))
id_heartbeat_channel = int(os.environ.get('ID_HEARTBEAT_CHANNEL', 0))
id_uptime_channel = int(os.environ.get('ID_UPTIME_CHANNEL', 0))


@tasks.loop(minutes=1)
async def heartbeat():
    '''Send a frequent heartbeat to a Discord channel for use in uptime reporting
    Have to run it with Exceptions suppressed, otherwise a single failed call will stop the whole loop'''
    with contextlib.suppress(Exception):
        heartbeat_channel = client.get_channel(id_heartbeat_channel)
        await heartbeat_channel.send(f"```{subprocess.check_output(['uptime']).decode().strip()}```")


@tasks.loop(hours=12)
async def uptime_report():
    '''Write out a daily uptime report to the specified channel, including hug and server statistics'''
    with contextlib.suppress(Exception):
        heartbeat_channel = client.get_channel(id_heartbeat_channel)
        uptime_channel = client.get_channel(id_uptime_channel)
        now = datetime.datetime.now()

        uptimestamps = [message.created_at.replace(microsecond=0) async for message in heartbeat_channel.history(limit=24*60*2+10) if (now - message.created_at).days == 0]
        uptime = len(uptimestamps) / (24 * 60)
        await uptime_channel.send(f'__**Uptime report for {now.isoformat()[:16]}**__:  {100*uptime:.2f}%')
        downtimes = [(earlier, later) for (earlier, later) in zip(uptimestamps[::-1], uptimestamps[-2::-1]) if abs(later - earlier) > datetime.timedelta(minutes=1, seconds=30)]
        for (earlier, later) in downtimes:
            await uptime_channel.send(f'* Went down at {earlier} for {later - earlier} :frowning:')
        if not downtimes:
            await uptime_channel.send('No downtime yay!! :hugging:')
        max_latency = max(timestamp.second for timestamp in uptimestamps) - min(timestamp.second for timestamp in uptimestamps)
        await uptime_channel.send(f'Maximum latency: {max_latency} seconds')
        await uptime_channel.send(f"```{subprocess.check_output(['uptime']).decode().strip()}```")
        await uptime_channel.send(f"```{subprocess.check_output(['free', '-h']).decode()[80:123]}```")
        await uptime_channel.send(f"```{subprocess.check_output(['df', '-h', '/']).decode().strip().splitlines()[-1]}```")
        await uptime_channel.send(f'Servers served: {len(client.guilds)}')
        await uptime_channel.send(f"Hugs (today/lifetime): {client.hug_cnt_day}/{len(open('log/hug_cnt_total').read())}")
        client.hug_cnt_day = 0


@client.event
async def on_ready():
    g = discord.Game(['I won\'t reply!', 'Use *hug help*!'][is_production])
    await client.change_presence(activity=g)

    logger.info('-' * 20)
    logger.info(f'On  Python version {platform.python_version()}  discord.py version {discord.__version__}')
    logger.info('Environment: %s', ['Testing', 'PRODUCTION!!'][is_production])
    logger.info('My name: %s', client.user)
    logger.info('Servers served: %s', str(len(client.guilds)))
    logger.info('I\'m in!!')
    logger.info('-' * 20)

    cooldown[id_admin] = float('-inf')  # immunity for Jan!


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
    '''Reply to a message. The author of the triggering messages gets a notch in the cooldown dictionary which automatically disappears after COOLDOWN_MINUTES'''
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


async def avatar_download_asynchronous(person_list):
    '''Download list of profile pictures, in 256x256, in parallel
    Pick animated GIF when available, else static PNG, else default avatar (= f'{discrim%5}.png')'''

    async def download(person, i):
        avatar_url = person.avatar_url_as(static_format='png', size=256)
        await avatar_url.save(f"avatar{i}")
        return f"avatar{i}"

    return await asyncio.gather(*(
        asyncio.create_task(download(person, i)) for i, person in enumerate(person_list)
    ))


# ------------------------------------

def only_run_if_activated(function):
    if os.environ['activate_feature_' + function.__name__] != 'True':
        return lambda *a, **b: asyncio.Future()
    return function


@only_run_if_activated
async def execute_code(message, i):
    '''run message as python code (very insecure, only used for the private version of the bot)'''

    code = message.content[i+1:].replace('```', '').replace('python', '')
    if any(badstr in code for badstr in ['open', 'token', 'os', 'sys', 'exit', 'import', 'subprocess', '_', 'rm']):
        return await send_message(message, '**You are trying to hack me. Incident reported to FBI CIA**')

    try:
        with io.StringIO() as buf:
            with contextlib.redirect_stdout(buf):
                exec(code, {}, {})
            await send_message(message, discord.utils.escape_mentions(buf.getvalue())[:2000])
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

        await message.attachments[0].save('attach')

        fn = hugify.apply_gif_save(['attach'], hugify.hugged, 'hugged.gif', maxsize=180)
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
        open('log/hug_cnt_total', 'a').write('.')


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
        await send_message(message, discord.utils.escape_mentions(message.content[::-1]))

    if 'good bot' == message_lower:
        await send_message(message, 'uwu')

    if 'uh' + '-' * (len(message_lower) - 2) == message_lower:
        await send_message(message, message_lower + '-')

    # hugify!! ^_^
    if message_lower.startswith('hug'):
        await hug(message, message_lower)

    if 'give autograph' in message_lower:
        author = message.author if message.author.id != id_admin or len(message.mentions) <= 1 else message.mentions[1]
        in_filenames = await avatar_download_asynchronous([author])
        top_text = f'To: {str(message.mentions[0])[:-5]}' if message.mentions else message.content[message_lower.find('autograph')+10:]
        fn = hugify.apply_gif_save([in_filenames[0]], hugify.autographed, texts=[str(author)[:-5], top_text] )
        return await send_file(message, '', fn, fn)


heartbeat.start()
uptime_report.start()
client.run(os.environ['DISCORD_BOT_SECRET'])
