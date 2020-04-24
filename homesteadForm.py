from discord.ext import commands
import discord
import yaml
from trello import TrelloClient
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import re
from gyazo import Api
from urllib.parse import urlparse
from os.path import splitext, basename
import aiohttp
import time
from sqlalchemy import *
import datetime
import pytz

client = commands.Bot(command_prefix='+')
with open(r'homesteadyConf.yaml') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    homesteadyConf = yaml.load(file, Loader=yaml.FullLoader)

    print(homesteadyConf)


@client.event
async def check_user_region(ctx):
    db_string = "postgres+psycopg2://postgres:{password}@{host}:{port}/postgres".format(username='root', password=homesteadyConf['postgres']['pwd'], host=homesteadyConf['postgres']['host'], port=homesteadyConf['postgres']['port'])
    db = create_engine(db_string, echo=True)
    metadata = MetaData(schema="homesteadProduction")

    with db.connect() as conn:
        discord_server_table = Table('discordIDServerMapping', metadata, autoload=True, autoload_with=conn)
        select_st = select([discord_server_table]).where(discord_server_table.c.discordID == ctx.author.id)
        res = conn.execute(select_st)
        user_info = res.first()
        if user_info is None:
            msg = await ctx.author.send("I think you're new here. Please select your server region:\n🗽 US\n⚽ SA\n🧀 EU\n🐨 OC")
            emoji_to_server_mapping = {
                "🗽": 'US',
                "⚽": 'SA',
                "🧀": 'EU',
                "🐨": 'OC'
            }
            await msg.add_reaction("🗽")
            await msg.add_reaction("⚽")
            await msg.add_reaction("🧀")
            await msg.add_reaction("🐨")
            try:
                region_reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=lambda reaction, user: reaction.emoji in ["🗽", "⚽", "🧀", "🐨"] and user != client.user and user.id == ctx.author.id)
                insert_statement = discord_server_table.insert().values(discordID=ctx.author.id, discordNicknameOrName=ctx.author.display_name or ctx.author.name, region=emoji_to_server_mapping[region_reaction.emoji])
                conn.execute(insert_statement)
                res = conn.execute(select_st)
                user_info = res.first()
            except Exception as err:
                print(err)
                await ctx.author.send("You've timed out. Please +home again.")
                conn.close()
                db.dispose()
                raise err
        server_timezone_mapping_table = Table('serverTimezoneMapping', metadata, autoload=True, autoload_with=conn)
        select_st = select([server_timezone_mapping_table]).where(server_timezone_mapping_table.c.server == user_info[2])
        res = conn.execute(select_st)
        server_timezone = res.first()
        await ctx.author.send(f"Your timezone is set in: {user_info[2]}")
        db.dispose()
        return server_timezone[1]

@client.event
async def change_user_region(ctx):
    db_string = "postgres+psycopg2://postgres:{password}@{host}:{port}/postgres".format(username='root', password=homesteadyConf['postgres']['pwd'], host=homesteadyConf['postgres']['host'], port=homesteadyConf['postgres']['port'])
    db = create_engine(db_string, echo=True)
    metadata = MetaData(schema="homesteadProduction")

    with db.connect() as conn:
        discord_server_table = Table('discordIDServerMapping', metadata, autoload=True, autoload_with=conn)
        select_st = select([discord_server_table]).where(discord_server_table.c.discordID == ctx.author.id)
        res = conn.execute(select_st)
        user_info = res.first()
        msg = await ctx.author.send("Please select your new server region:\n🗽 US\n⚽ SA\n🧀 EU\n🐨 OC")
        emoji_to_server_mapping = {
            "🗽": 'US',
            "⚽": 'SA',
            "🧀": 'EU',
            "🐨": 'OC'
        }
        await msg.add_reaction("🗽")
        await msg.add_reaction("⚽")
        await msg.add_reaction("🧀")
        await msg.add_reaction("🐨")
        try:
            region_reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=lambda reaction, user: reaction.emoji in ["🗽", "⚽", "🧀", "🐨"] and user != client.user and user.id == ctx.author.id)
            update_statement = discord_server_table.update().values(region=emoji_to_server_mapping[region_reaction.emoji]).where(discord_server_table.c.discordID == ctx.author.id)
            conn.execute(update_statement)
        except Exception as err:
            await ctx.author.send("You've timed out. Please +home again.")
            conn.close()
            db.dispose()
            raise err
    db.dispose()


@client.command(pass_context=True, name='home')
async def send_harvest_form(ctx):
    not_timeout = True
    try:
        await ctx.message.add_reaction("✅")
        msg = await ctx.author.send("Please select up to three production categories you'd like a reminder for:\n🌿 Herbs\n🐰 Beasts\n⚒ Ores\nThen press the :white_check_mark:\n\n **Confirm** :white_check_mark:\n **Cancel** ❌")
        await msg.add_reaction("🌿")
        await msg.add_reaction("🐰")
        await msg.add_reaction("⚒")
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        try:
            submit_reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=lambda reaction, user: reaction.emoji in ["✅", "❌"] and user != client.user and user.id == ctx.author.id)
        except Exception as err:
            await ctx.author.send("You've timed out. Please +home again.")
            raise err
        # print(herbs_reaction, beasts_reaction, ores_reaction, submit_reaction)
        if not_timeout:
            channel = discord.utils.get([channel for channel in client.private_channels if channel.recipient.id == ctx.author.id])
            time.sleep(2)
            cached_msg = await channel.fetch_message(msg.id)
            emoji_to_crop_mapping = {
                "🌿": "herbs",
                "🐰": "beasts",
                "⚒": "ores"
            }
            categories_to_be_reminded_for = []
            if cached_msg.reactions[4].count > 1:
                await ctx.author.send("Very well you've canceled your request for a reminder.")
            elif cached_msg.reactions[3].count > 1 and cached_msg.reactions[0].count == 1 and cached_msg.reactions[1].count == 1 and cached_msg.reactions[2].count == 1:
                await ctx.author.send("By default, you've chosen all 3 categories to be reminded for.")
                categories_to_be_reminded_for = ["herbs", "beasts", "ores"]
                await start_session(ctx, categories_to_be_reminded_for)
            else:
                categories_to_be_reminded_for += [emoji_to_crop_mapping[reaction.emoji] for reaction in cached_msg.reactions[0:3] if reaction.count > 1]
                await start_session(ctx, categories_to_be_reminded_for)
    except Exception as err:
        print(err)

@client.event
async def start_session(ctx, categories):
    try:
        db_string = "postgres+psycopg2://postgres:{password}@{host}:{port}/postgres".format(username='root', password=homesteadyConf['postgres']['pwd'], host=homesteadyConf['postgres']['host'], port=homesteadyConf['postgres']['port'])
        db = create_engine(db_string)
        metadata = MetaData(schema="homesteadProduction")
        four_hour_reminder_crops = []
        eight_hour_reminder_crops = []
        twelve_hour_reminder_crops = []
        for category in categories:
            with db.connect() as conn:
                table = Table(category, metadata, autoload=True, autoload_with=conn)
                menu_msg =[f"Please select up to 8 {category} you'd like a reminder for:"]
                select_st = select([table])
                res = conn.execute(select_st)
                selections = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
                emoji_to_crop_mapping = {}
                crop_results= []
                i = 0
                for _row in res:
                    menu_msg.append(f"\n{selections[i]} {_row[0]} : {_row[1]} hrs")
                    crop_results.append((_row[0], _row[1]))
                    i += 1
                menu_msg.append("\nThen press the :white_check_mark:")
                msg = await ctx.author.send(" ".join(menu_msg))
                for emoji in selections:
                    await msg.add_reaction(emoji)
                await msg.add_reaction("✅")
                await msg.add_reaction("❌")
                try:
                    submit_reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=lambda reaction, user: reaction.emoji in ["✅", "❌"] and user != client.user and user.id == ctx.author.id)
                except Exception as err:
                    await ctx.author.send("You've timed out. Please +home again.")
                    conn.close()
                    db.dispose()
                    raise err
                if user.id == ctx.author.id:
                    channel = discord.utils.get([channel for channel in client.private_channels if channel.recipient.id == ctx.author.id])
                    time.sleep(2)
                    cached_msg = await channel.fetch_message(msg.id)
                    i = 0
                    for reaction in cached_msg.reactions[0:8]:
                        emoji_to_crop_mapping[reaction.emoji] = crop_results[i]
                        i += 1
                    canceled = len(list(filter(lambda reaction: reaction.emoji in ["❌"], cached_msg.reactions))) > 1
                    if not canceled:
                        selected_reactions = [reaction.emoji for reaction in cached_msg.reactions if reaction.count > 1 and reaction.emoji not in ["✅", "❌"]]
                        if len(selected_reactions) < 1:
                            await ctx.author.send("You did not select any crops")
                        else:
                            await ctx.author.send(f'You\'ve selected the following crops: {", ".join([emoji_to_crop_mapping[reaction][0] for reaction in selected_reactions])}')
                            four_hour_reminder_crops += [emoji_to_crop_mapping[reaction][0] for reaction in selected_reactions if emoji_to_crop_mapping[reaction][1] == 4]
                            eight_hour_reminder_crops += [emoji_to_crop_mapping[reaction][0] for reaction in selected_reactions if emoji_to_crop_mapping[reaction][1] == 8]
                            twelve_hour_reminder_crops += [emoji_to_crop_mapping[reaction][0] for reaction in selected_reactions if emoji_to_crop_mapping[reaction][1] == 12]
                    else:
                        await ctx.author.send("You have canceled this category's session")
        with db.connect() as conn:
            table = Table('alarms', metadata, autoload=True, autoload_with=conn)
            if len(four_hour_reminder_crops) > 0:
                await confirm_time(ctx, conn, table, four_hour_reminder_crops, 4)
            if len(eight_hour_reminder_crops) > 0:
                await confirm_time(ctx, conn, table, eight_hour_reminder_crops, 8)
            if len(twelve_hour_reminder_crops) > 0:
                await confirm_time(ctx, conn, table, twelve_hour_reminder_crops, 12)

        db.dispose()
    except Exception as err:
        print(f"Error: {err}")

@client.event
async def confirm_time(ctx, conn, table, reminder_crops_array, hours_reminder):
    timezone_set = False
    timezone = await check_user_region(ctx)
    time_now = datetime.datetime.combine(datetime.date.today(), datetime.datetime.now().time())
    displayed_time_now = datetime.datetime.now(pytz.timezone(timezone))
    reminder_time = time_now + datetime.timedelta(hours=hours_reminder - 1, minutes=52)
    displayed_reminder_time = displayed_time_now + datetime.timedelta(hours=hours_reminder - 1, minutes=52)
    await ctx.author.send(f'You will be reminded at {displayed_reminder_time.time().replace(microsecond=0).strftime("%H:%M")} for the following products: {", ".join(reminder_crops_array)}')
    prompt_check_reminder = await ctx.author.send('Press ✅ if this is okay with you\nor ⏰ to tell us in how many minutes you would like to be reminded\nor 🗺️ to change your timezone')
    await prompt_check_reminder.add_reaction("✅")
    await prompt_check_reminder.add_reaction("⏰")
    try:
        submit_reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=lambda reaction, user: reaction.emoji in ["✅", "⏰"] and user != client.user and user.id == ctx.author.id)
    except Exception as err:
        await ctx.author.send("You've timed out. Please +home again.")
        conn.close()
        raise err
    if submit_reaction.emoji == "✅" and user.id == ctx.author.id:
        insert_statement = table.insert().values(discordID=ctx.author.id, discordNicknameOrName=ctx.author.display_name or ctx.author.name, timeToNotify=reminder_time, displayedTimeToNotify=displayed_reminder_time.replace(tzinfo=None), itemsWComma=", ".join(reminder_crops_array))
        conn.execute(insert_statement)
        await ctx.author.send(f'We have placed a {hours_reminder}-hour reminder for you for the following products: {", ".join(reminder_crops_array)}')
    elif submit_reaction.emoji == "⏰" and user.id == ctx.author.id:
        await resend_form(ctx, user.id, conn, table, time_now, displayed_time_now, reminder_crops_array)


@client.event
async def resend_form(ctx, id,  conn, table, time_now, displayed_time_now, reminder_crops_array):
    is_a_valid_response = False
    await ctx.author.send("In about how many more minutes would you like to receive your reminder? 200 minutes? Let me know.")
    response_msg = await client.wait_for('message', check=check)
    if hasNumbers(response_msg.clean_content):
        reminder_time = time_now + datetime.timedelta(minutes=int(re.findall("\d+", response_msg.clean_content)[0]))
        displayed_reminder_time = displayed_time_now + datetime.timedelta(minutes=int(re.findall("\d+", response_msg.clean_content)[0]))
        await ctx.author.send(f'You will be reminded at {displayed_reminder_time.time().replace(microsecond=0).strftime("%H:%M")} for the following products: {", ".join(reminder_crops_array)}')
        prompt_check_reminder = await ctx.author.send('Press ✅ if this is okay with you or ⏰ to tell us in how many minutes you would like to be reminded')
        await prompt_check_reminder.add_reaction("✅")
        await prompt_check_reminder.add_reaction("⏰")
        try:
            submit_reaction, user = await client.wait_for('reaction_add', timeout=600.0, check=lambda reaction, user: reaction.emoji in ["✅", "⏰"] and user != client.user and user.id == id)
        except Exception as err:
            await ctx.author.send("You've timed out. Please +home again.")
            conn.close()
            raise err
        if submit_reaction.emoji == "✅" and user.id == id:
            insert_statement = table.insert().values(discordID=id, discordNicknameOrName=ctx.author.display_name or ctx.author.name, timeToNotify=reminder_time, displayedTimeToNotify=displayed_reminder_time.replace(tzinfo=None), itemsWComma=", ".join(reminder_crops_array))
            conn.execute(insert_statement)
            await ctx.author.send(f"Your reminder for {displayed_reminder_time.time().replace(microsecond=0).strftime('%H:%M')} has been confirmed")
        elif submit_reaction.emoji == "⏰" and user.id == id:
            await resend_form(ctx, id, conn, table, time_now, displayed_time_now, reminder_crops_array)

def check(message):
    return message.channel.type == discord.ChannelType.private

def hasNumbers(inputString):
    return any(char.isdigit() for char in inputString)
def cancel_session(message):
    return message.clean_content == "!cancel"

# test token
# client.run(homesteadyConf['test_bot_token'])
# pwm token
client.run(homesteadyConf['bot_token'])

# pm2 reload homesteadForm.py --interpreter=python3
# pm2 start homesteadForm.py --interpreter=python3
