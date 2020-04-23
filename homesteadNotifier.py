from sqlalchemy import *
from discord.ext import commands
import yaml
import datetime


client = commands.Bot(command_prefix='+')
with open(r'homesteadyConf.yaml') as file:
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    homesteadyConf = yaml.load(file, Loader=yaml.FullLoader)

    print(homesteadyConf)

@client.event
async def on_ready():
    print('Bot is ready.')
    while True:
        try:
            await check_if_reminder_needed()
        except Exception as err:
            print(err)

async def check_if_reminder_needed():
    db_string = "postgres+psycopg2://postgres:{password}@{host}:{port}/postgres".format(username='root', password=homesteadyConf['postgres']['pwd'], host=homesteadyConf['postgres']['host'], port=homesteadyConf['postgres']['port'])
    db = create_engine(db_string)
    metadata = MetaData(schema="homesteadProduction")

    with db.connect() as conn:
        table = Table('alarms', metadata, autoload=True, autoload_with=conn)
        select_st = select([table]).where(cast(table.c.timeToNotify, Date) == datetime.datetime.today().date())
        res = conn.execute(select_st)
        for _row in res:
            user = client.get_user(_row[0])
            past = datetime.datetime.now() - datetime.timedelta(seconds=60)
            future = datetime.datetime.now() + datetime.timedelta(seconds=60)

            if _row[2].time() > past.time() and _row[2].time() < future.time():
                await user.send(f"Hello! You have a Homestead reminder for {_row[3].time().replace(microsecond=0).strftime('%H:%M')}\nGet your items: {_row[4]}")
                delete_entry = table.delete().where(
                    and_(
                        table.c.discordID == _row[0],
                        table.c.timeToNotify == _row[2]
                    )
                )
                conn.execute(delete_entry)
    db.dispose()

client.run(homesteadyConf['bot_token'])

# pm2 reload homesteadNotifier.py --interpreter=python3

