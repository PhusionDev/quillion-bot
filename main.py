import os
import json
from google.oauth2.service_account import Credentials
from discord.ext import commands
import discord
import gspread
import datetime

bot = commands.Bot(command_prefix='!')

TOKEN = os.getenv("DISCORD_TOKEN")
json_creds = os.getenv("GOOGLE_SHEETS_CREDS_JSON")

# use creds to create a client to interact with the Google Drive API
scopes = ['https://spreadsheets.google.com/feeds']

creds_dict = json.loads(json_creds)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\\\n", "\n")

sa = gspread.service_account_from_dict(creds_dict)
sh = sa.open("Quillion CRO Whitelist")

wks_db = sh.worksheet("UUID Table")
wks_db_records = {}
names = {}
uuids = {}
last_db_datetime = datetime.datetime.now() - datetime.timedelta(hours=1)
fetching = False

def update_db():
  global last_db_datetime
  global fetching
  global wks_db_records
  global wks_db_records
  global names
  global uuids
  dt = datetime.datetime.now()
  dd = dt - last_db_datetime
  if (dd.seconds > 60):
    if not fetching:
      fetching = True
      print("Debug: last db update over 60s ago, fetching data")
      records = wks_db.get_all_records()
      last_db_datetime = dt
      fetching = False
      if wks_db_records != records:
        wks_db_records = records
        print("Debug: Records list has changed")
        uuids = {d['ID']:d['UUID'] for d in wks_db_records}
        names = {d['ID']:d['Name'] for d in wks_db_records}
      else:
        print("Debug: No records have been changed")

def get_uuid(user_id):
  uuid = None
  update_db()
  if (user_id in uuids):
    uuid = uuids[user_id]
    print(f'{user_id}\'s UUID: {uuid}')
  return uuid

def get_name(user_id):
  name = None
  update_db()
  if (user_id in names):
    name = names[user_id]
    print(f'{user_id}\'s name: {name}')
  return name

@bot.command()
async def WL(ctx):
  message = None
  if (ctx.message.channel.name == '🦔︱wl-bot'):
    print(f'user id: {ctx.author.id}')
    uuid = get_uuid(ctx.author.id)
    if (uuid):
      message = f'Your Verify Code is: {uuid}'
    else:
      message = f'Sorry you are not on the whitelist!'
    try:
      await ctx.author.send(message)
    except discord.Forbidden:
      pass

bot.run(TOKEN)
