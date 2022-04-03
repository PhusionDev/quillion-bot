import os
import re
import json
from google.oauth2.service_account import Credentials
from discord.ext import commands
import discord
import gspread
import datetime

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

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

admins = {'150380581723701250': True}
names = {}
uuids = {}
rolemembers = []
newmembers = {}
retiredmembers = {}

last_db_datetime = datetime.datetime.now() - datetime.timedelta(hours=1)
fetching = False

# Internal Functions

# Utility / Helper
def is_admin(user_id):
  if str(user_id) in admins:
    return admins[str(user_id)]

def get_value(str):
  print(f'Getting value for: {str}')
  str = strip_at_bang(str)
  print(f'Getting value for: {str}')
  try:
    return int(str)
  except ValueError:
    return None

def strip_at_bang(ab_str):
  return re.sub('[<>@!]*','',ab_str)

def generate_csv(dict, title="Dict to CSV"):
  csv_str = f'```{title} | Rows: {len(dict)}\n'
  for k in dict.keys():
    csv_str += f'{dict[k]},{k}\n'
  csv_str += f'```'
  return csv_str

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
        for d in wks_db_records:
          if not d['ID'] == "":
            uuids[d['ID']] = d['UUID']
            names[d['ID']] = d['Name']
        print(f'uuids: {len(uuids.keys())} | names: {len(names.keys())}')
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

# BOT COMMANDS

# Whitelist Command
@bot.command()
async def WL(ctx):
  message = None
  if (ctx.message.channel.name == '🦔︱wl-bot'):
    print(f'user id: {ctx.author.id}')
    uuid = get_uuid(ctx.author.id)
    if (uuid):
      message = f'Please visit https://forms.gle/VbEbptp6zq1RPns59 to fill out the WL form\nYour Verify Code is:\n{uuid}\nPlease do not share this code or your entry may be invalidated!'
    else:
      message = f'Sorry you are not on the whitelist!'
    try:
      await ctx.author.send(message)
    except discord.Forbidden:
      pass

# Role Check Command
@bot.command()
async def rolecheck(ctx, *, role="Hedgies WL (CRO)"):
  global rolemembers
  if is_admin(ctx.author.id):
    update_db()
    role = strip_at_bang(role)
    rolemembers = []
    newmembers = {}
    retiredmembers = {}
    print(f'searching for role: {role}')
    for member in ctx.guild.members:
      # print(f'Checking if {member.name} belongs to {role} role')
      for r in member.roles:
          if r.name == role:
            # names[str(member.id)] = member.name
            rolemembers.append(member.id)
            if not (member.id in names):
              # print(f'{member.id}: {member.name} is a new role member')
              newmembers[member.id] = member.name
    for k in names:
      # print(f'role checking id: {k}')
      if not (k in rolemembers):
        print(f'{k}: {names[k]} has been retired')
        retiredmembers[k] = names[k]
    # print(f'Members in {role} role:\n{rolemembers}')
    count_roles = len(rolemembers)
    count_names = len(names.keys())
    await ctx.channel.send(f'Members in WL DB: {count_names} | Members with {role} role: {count_roles}')
    if len(newmembers) > 0:
      csv_new = generate_csv(newmembers,"New Members")
      if len(newmembers) < 20:
        await ctx.channel.send(csv_new)
      else:
        await ctx.channel.send(f'```20+ new members, too many to display; check logs```')
        print(csv_new)
    if len(retiredmembers) > 0:
      csv_retired = generate_csv(retiredmembers, "Retired Members")
      if len(retiredmembers) < 20:
        await ctx.channel.send(csv_retired)
      else:
        await ctx.channel.send(f'```20+ retired members, too many to display; check logs```')
        print(csv_retired)
  else:
    print(f'User: {ctx.author.id} is not authorized')

bot.run(TOKEN)
