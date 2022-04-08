import os
import re
import json
import datetime
import gspread
import nextcord
from nextcord import Interaction
from nextcord.ext import commands

intents = nextcord.Intents.default()
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

wks_config = sh.worksheet("Config")
wks_config_records = {}

wks_valid_entries = sh.worksheet("Parsed Responses")
wks_valid_entries_records = {}

guilds = [937228523964346440]
admins = {150380581723701250: True}
valid_entries = {}
names = {}
uuids = {}
rolemembers = []
newmembers = {}
retiredmembers = {}
num_entries = {}

last_db_datetime = datetime.datetime.now() - datetime.timedelta(hours=1)
fetching = False

# Internal Functions

# Utility / Helper
def is_admin(user_id):
  if user_id in admins:
    return admins[user_id]

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

def update_uuid_records(records_uuids):
  global uuids
  global names
  global wks_db_records
  if wks_db_records != records_uuids:
    wks_db_records = records_uuids
    uuids = {}
    names = {}
    print("Debug: UUID Records list has changed")
    for d in wks_db_records:
      if not d['ID'] == "":
        uuids[d['ID']] = d['UUID']
        names[d['ID']] = d['Name']
    print(f'uuids: {len(uuids.keys())} | names: {len(names.keys())}')

def update_config_records(records_config):
  global admins
  global wks_config_records
  if wks_config_records != records_config:
    wks_config_records = records_config
    new_admins = {}
    print("Configuration settings have changed")
    for d in wks_config_records:
      if not d['admin_id'] == "":
        new_admins[d['admin_id']] = True
    admins = new_admins
    if not 150380581723701250 in admins:
      admins[150380581723701250] = True
    print(f'# of admins: {len(admins)} | Admins List:\n{admins}')

def update_valid_entries_records(records_valid_entries):
  global wks_valid_entries_records
  global valid_entries
  global num_entries
  if wks_valid_entries_records != records_valid_entries:
    wks_valid_entries_records = records_valid_entries
    valid_entries = {}
    num_entries = {}
    print(f'Valid entries have changed')
    for d in wks_valid_entries_records:
      if not d['user id'] == "":
        id = d['user id']
        if not id in num_entries:
          num_entries[id] = 1
        else:
          num_entries[id] += 1
        info_dict = {}
        info_dict["name"] = d["Discord User"]
        info_dict["wallet"] = d["Address"]
        info_dict["qty"] = d["Qty"]
        valid_entries[id] = info_dict
    print(f'Valid Entries: {len(valid_entries)}')

def update_db():
  global last_db_datetime
  global fetching
  dt = datetime.datetime.now()
  dd = dt - last_db_datetime
  if (dd.seconds > 60):
    if not fetching:
      fetching = True
      print("Debug: last db update over 60s ago, fetching data")
      records_db = wks_db.get_all_records()
      records_config = wks_config.get_all_records()
      records_valid_entries = wks_valid_entries.get_all_records()
      last_db_datetime = dt
      fetching = False
      update_uuid_records(records_db)
      update_config_records(records_config)
      update_valid_entries_records(records_valid_entries)
      
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

def has_role(member):
  for r in member.roles:
    if r.name == "Hedgies WL (CRO)":
      return True
  return False

def wl_sorry(name):
  message = f'Sorry, {name}, but you are not on the whitelist! :x:\nPlease stay tuned for opportunities to join the whitelist!'
  return message

def wl_info(uuid):
  message = f':page_facing_up: Whitelist Form :page_facing_up:\nhttps://forms.gle/VbEbptp6zq1RPns59\n\n:closed_lock_with_key: Your Verify Code :closed_lock_with_key:\n```{uuid}```\n:exclamation: **Please do not share this code or your entry may be invalidated!** :exclamation:'
  return message

def wl_waiting_db(name):
  message = f'Hello {name},\nYou have the WL role :white_check_mark:\nYou are on the whitelist :white_check_mark:\nBut your information has not been entered into the database yet :x:\nWe are updating the DB regularly as users earn the role\nPlease try again in a little while or message an admin'
  return message

def wl_greeting_new(name):
  message = f'`Hello {name}! Here is your information for Quillion\'s Cronos Whitelist:`'
  return message

def wl_greeting_existing(name, id):
  num = num_entries[id]
  entry_str = "entry" if num == 1 else "entries"
  message = f'Hello {name} you have already submitted **{num_entries[id]}** valid {entry_str}.\nYour most recent submission will be used:'
  return message

def condensed_users_str(user_dict):
  user_str = ''
  for user_id in user_dict.keys():
    user_str += f'<@{user_id}>'
  return user_str

# BOT COMMANDS

@bot.slash_command(name="bothroles", description="get members in multiple roles",guild_ids=guilds)
async def inroles(interaction: Interaction):
  role1 = "Hedgies WL"
  role2 = "Hedgies WL (CRO)"
  if is_admin(interaction.user.id):
    dual_roles = {}
    for member in interaction.guild.members:
      member_id = member.id
      roles = {"role1": False, "role2": False}
      for r in member.roles:
        if r.name == role1:
          roles["role1"] = True
        if r.name == role2:
          roles["role2"] = True
      if roles["role1"] and roles["role2"]:
        dual_roles[member.id] = member.name
    user_str = condensed_users_str(dual_roles)
    if len(user_str) <= 2000:
      message = user_str
    else:
      print(dual_roles)
      message = f'# of Members with both roles: {len(dual_roles.keys())}\nExceeds discord message character limit, check logs.'
    await interaction.response.send_message(message)

@bot.slash_command(name="whitelist", description="get whitelist information", guild_ids=guilds)
async def wl(interaction: Interaction):
  message=wl_sorry(interaction.user.name)
  if has_role(interaction.user):
    uuid = get_uuid(interaction.user.id)
    if interaction.user.id in valid_entries:
      id = interaction.user.id
      name = valid_entries[id]["name"]
      wallet = valid_entries[id]["wallet"]
      qty = valid_entries[id]["qty"]
      message = f'{wl_greeting_existing(interaction.user.name, id)}\n```Name: {name}\nWallet Address: {wallet}\nQty: {qty}```\n\n`If you need to make changes, please submit another entry.`\n\n{wl_info(uuid)}'
    else:
      if (uuid):
        message = f'{wl_greeting_new(interaction.user.name)}\n\n{wl_info(uuid)}'
      else:
        message = wl_waiting_db(interaction.user.name)
  await interaction.response.send_message(message, ephemeral=True)

# Whitelist Command
@bot.command()
async def WL(ctx):
  message=wl_sorry(ctx.author.name)
  if has_role(ctx.author):
    uuid = get_uuid(ctx.author.id)
    if ctx.author.id in valid_entries:
      id = ctx.author.id
      name = valid_entries[id]["name"]
      wallet = valid_entries[id]["wallet"]
      qty = valid_entries[id]["qty"]
      message = f'{wl_greeting_existing(ctx.author.name, id)}\n```Name: {name}\nWallet Address: {wallet}\nQty: {qty}```\n\n`If you need to make changes, please submit another entry.`\n\n{wl_info(uuid)}'
    else:
      if (uuid):
        message = f'{wl_greeting_new(ctx.author.name)}\n\n{wl_info(uuid)}'
      else:
        message = wl_waiting_db(ctx.author.name)
  try:
    await ctx.author.send(message)
  except nextcord.Forbidden:
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
              # print(f'{member.id}: {member} is a new role member')
              newmembers[member.id] = member
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

@bot.event
async def on_ready():
  print("The bot is now ready for use! Updating DBs")
  update_db()

bot.run(TOKEN)
