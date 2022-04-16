import os
import re
import json
import datetime
import gspread
import nextcord
import random
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

# UUID TABLE WORKSHEET AND RECORDS DICTIONARY #
wks_db = sh.worksheet("UUID Table")
wks_db_records = {}

# CONFIG/ADMIN WORKSHEET AND RECORDS DICTIONARY #
wks_config = sh.worksheet("Config")
wks_config_records = {}

# VALID ENTRIES WORKSHEET AND RECORDS DICTIONARY #
wks_valid_entries = sh.worksheet("Parsed Responses")
wks_valid_entries_records = {}

# SERVER UNIQUE VALUES #
guilds = [937228523964346440]
wl_role_id = 958467891760627722

# ADMINS LIST - AGENTBABS BY DEFAULT #
admins = {150380581723701250: True}

# APPLICATION LISTS / DICTIONARIES #
filter_ids = ["99999999999999999900"]
valid_entries = {}
names = {}
uuids = {}
rolemembers = []
newmembers = {}
retiredmembers = {}
num_entries = {}

# ESTABLISH LAST DB UDPATE #
last_db_datetime = datetime.datetime.now() - datetime.timedelta(hours=1)
fetching = False

# # # INTERNAL FUNCTIONS # # #

# # UTILITY / HELPER FUNCTIONS # #

# CHECK FOR USER IS AN ADMIN #
def is_admin(user_id):
  if user_id in admins:
    return admins[user_id]

def is_filtered_id(id):
  if str(id) in filter_ids:
    return True
  return False

# STRIP CHANNEL ID SIGNATURE #
def clean_channel(ab_str):
  return re.sub('[<>@!]*','',ab_str)

# STRIP ROLE ID SIGNATURE #
def clean_role(role):
  return re.sub('[<>@&]*', '', role)

# STRIP USER ID SIGNATURE #
def clean_user(user_str):
  return re.sub('[<>@]*', '', user_str)

# GET UUID FOR USER ID #
def get_uuid(user_id):
  uuid = None
  update_db()
  if (user_id in uuids):
    uuid = uuids[user_id]
    print(f'{user_id}\'s UUID: {uuid}')
  return uuid

# GET NAME FOR USER ID #
def get_name(user_id):
  name = None
  update_db()
  if (user_id in names):
    name = names[user_id]
    print(f'{user_id}\'s name: {name}')
  return name

# CHECK IF MEMBER HAS A CERTAIN ROLE #
def has_role(member, role_name):
  for r in member.roles:
    if r.name == role_name:
      return True
  return False

# GET ROLE OBJECT FROM VARIOUS STRING FORMATS #
async def get_role(guild, role_str):
  role = None
  role_str = clean_role(role_str)
  if is_value(role_str):
    role = nextcord.utils.get(guild.roles, id=int(role_str))
  else:
    role = nextcord.utils.get(guild.roles, name=role_str)
  return role

# GENERATE A CSV FROM DICTIONARY #
def generate_csv(dict, title="Dict to CSV"):
  csv_str = f'```{title} | Rows: {len(dict)}\n'
  for k in dict.keys():
    csv_str += f'{dict[k]},{k}\n'
  csv_str += f'```'
  return csv_str

# # UPDATE FUNCTIONS # #

# UPDATE UUID TABLE RECORDS #
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
      user_id = d['ID']
      if not user_id == "":
        if not is_filtered_id(user_id):
          uuids[user_id] = d['UUID']
          names[user_id] = d['Name']
        else:
          print(f'Found filtered id: {user_id}: {d["Name"]}')
    print(f'uuids: {len(uuids.keys())} | names: {len(names.keys())}')

# UPDATE CONFIG / ADMIN RECORDS #
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

# UPDATE VALID SUBMISSIONS / ENTRIES #
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

# UPDATE ENTIRE DATABASE #
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
      
# # HELPER MESSAGE FUNTIONS # #

# SORRY NOT ON WHITELIST MESSAGE #
def wl_sorry(name):
  message = f'Sorry, {name}, but you are not on the whitelist! :x:\nPlease stay tuned for opportunities to join the whitelist!'
  return message

# USER'S WHITELIST INFO MESSAGE #
def wl_info(uuid):
  message = f':page_facing_up: Whitelist Form :page_facing_up:\nhttps://forms.gle/VbEbptp6zq1RPns59\n\n:closed_lock_with_key: Your Verify Code :closed_lock_with_key:\n```{uuid}```\n:exclamation: **Please do not share this code or your entry may be invalidated!** :exclamation:'
  return message

# WAITING FOR BACKEND UPDATE MESSAGE #
def wl_waiting_db(name):
  message = f'Hello {name},\nYou have the WL role :white_check_mark:\nYou are on the whitelist :white_check_mark:\nBut your information has not been entered into the database yet :x:\nWe are updating the DB regularly as users earn the role\nPlease try again in a little while or message an admin'
  return message

# GREETING NEW WL USER MESSAGE #
def wl_greeting_new(name):
  message = f'`Hello {name}! Here is your information for Quillion\'s Cronos Whitelist:`'
  return message

# GREETING EXISTING WL USER MESSAGE #
def wl_greeting_existing(name, id):
  num = num_entries[id]
  entry_str = "entry" if num == 1 else "entries"
  message = f'Hello {name} you have already submitted **{num_entries[id]}** valid {entry_str}.\nYour most recent submission will be used:'
  return message

# GENERATES STRING OF PINGABLE USERS FROM DICTIONARY WITH USER ID KEYS #
def condensed_users_str(user_dict):
  user_str = ''
  for user_id in user_dict.keys():
    user_str += f'<@{user_id}>'
  return user_str

# GENERATES STRING OF PINGABLE USERS FROM LIST OF MEMBER OBJECTS #
def condensed_members_str(members):
  user_str = ''
  for member in members:
    user_str += f'<@{member.id}>'
  return user_str

# RETURNS A STRING WITH PINGABLE USER ID FROM USER ID #
def ping_user_str(id):
  return f'<@{id}>'

# CHECKS IF A STRING CONTAINS A VALUE OR NOT #
def is_value(str):
  try:
    int(str)
    return True
  except ValueError:
    return False

# RETURNS THE CURRENT NAME OF THE ASSIGNED WL ROLE'S ID #
async def get_wl_role_name(guild):
  role = await get_role(guild, str(wl_role_id))
  if role:
    return role.name
  else:
    return "Invalid Role ID In Settings"

# # # BOT COMMANDS # # #

# # SLASH COMMANDS # #

# CHECK FOR WL MEMBERS WITHOUT AN ENTRY SUBMISSION #
@bot.slash_command(name="noentry", description="list members with WL role but no form entry", guild_ids=guilds)
async def noentry(interaction: Interaction):
  message = f'Sorry {interaction.user.name}, but you are not authorized to use this command'
  if is_admin(interaction.user.id):
    wl_role_name = await get_wl_role_name(interaction.guild)
    message = "checking for users without an entry"
    members_str = ""
    update_db()
    count = 0
    for member in interaction.guild.members:
      for r in member.roles:
        if r.name == wl_role_name:
          if not member.id in valid_entries:
            count += 1
            members_str += f'<@{member.id}>'
          break
    long_message = f'Number of users without a WL submission: {count}\n{members_str}'
    if len(message) < 2000:
      message = long_message
    else:
      message = f'Number of users without a WL submission **{count}** exceeds character count\nCheck logs...'
      print(long_message)
  await interaction.response.send_message(message, ephemeral=True)

# CHECK FOR WL MEMBERS WITHOUT AN ENTRY SUBMISSION FILTER TEAM MEMBERS #
@bot.slash_command(name="noentryf", description="list members with WL role but no form entry", guild_ids=guilds)
async def noentryf(interaction: Interaction):
  message = f'Sorry {interaction.user.name}, but you are not authorized to use this command'
  if is_admin(interaction.user.id):
    filters = ["Board Member", "Trustee", "Founder", "Hedgie Admin"]
    wl_role_name = await get_wl_role_name(interaction.guild)
    message = "checking for users without an entry"
    members_str = ""
    update_db()
    count = 0
    # Build initial list of members with WL role
    for member in interaction.guild.members:
      filter_member = False
      has_wl_role = False
      roles = []
      for role in member.roles:
        roles.append(role.name)
      if wl_role_name in roles:
        has_wl_role = True
      for frole in filters:
        if frole in roles:
          filter_member = True
          break
      if has_wl_role and not filter_member:
        if not member.id in valid_entries:
          count += 1
          members_str += f'<@{member.id}>'
    long_message = f'Number of users without a WL submission: {count}\n{members_str}'
    if len(message) < 2000:
      message = long_message
    else:
      message = f'Number of users without a WL submission **{count}** exceeds character count\nCheck logs...'
      print(long_message)
  await interaction.response.send_message(message)

# CHECK FOR WL MEMBERS WITHOUT AN ENTRY SUBMISSION TEAM MEMBERS ONLY #
@bot.slash_command(name="noentryt", description="list members with WL role but no form entry", guild_ids=guilds)
async def noentryt(interaction: Interaction):
  message = f'Sorry {interaction.user.name}, but you are not authorized to use this command'
  if is_admin(interaction.user.id):
    includes = ["Board Member", "Trustee", "Founder", "Hedgie Admin"]
    wl_role_name = await get_wl_role_name(interaction.guild)
    message = "checking for users without an entry"
    members_str = ""
    update_db()
    count = 0
    # Build initial list of members with WL role
    for member in interaction.guild.members:
      include_member = False
      has_wl_role = False
      roles = []
      for role in member.roles:
        roles.append(role.name)
      if wl_role_name in roles:
        has_wl_role = True
      for irole in includes:
        if irole in roles:
          include_member = True
          break
      if has_wl_role and include_member:
        if not member.id in valid_entries:
          count += 1
          members_str += f'<@{member.id}>'
    long_message = f'Team members without a WL submission: {count}\n{members_str}'
    if len(message) < 2000:
      message = long_message
    else:
      message = f'Number of users without a WL submission **{count}** exceeds character count\nCheck logs...'
      print(long_message)
  await interaction.response.send_message(message)

# WHITELIST INFORMATION SLASH COMMAND #
@bot.slash_command(name="whitelist", description="get whitelist information", guild_ids=guilds)
async def wl(interaction: Interaction):
  wl_role_name = await get_wl_role_name(interaction.guild)
  message=wl_sorry(interaction.user.name)
  if has_role(interaction.user, wl_role_name):
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

# # NORMAL COMMANDS # #

# RANDOM WL GIVEAWAY COMMAND #
@bot.command()
async def wlrand(ctx, rolename_entry, rolename_giveaway, qty:int=1):
  message = f'Sorry {ctx.author.name}, but you are not authorized'
  if is_admin(ctx.author.id):
    if qty > 0:
      role_entry = await get_role(ctx.guild, rolename_entry)
      if role_entry == None:
        await ctx.channel.send(f'Entry role invalid')
      else:
        role_giveaway = await get_role(ctx.guild, rolename_giveaway)
        if role_giveaway == None:
          await ctx.channel.send(f'Giveaway role invalid')
        else:
          rolename_entry = role_entry.name
          rolename_giveaway = role_giveaway.name
          print(f'Entry Role: {rolename_entry} | Giveaway Role: {rolename_giveaway}')
          members = []
          # get list of members with role specified
          for member in ctx.guild.members:
            if has_role(member, rolename_entry):
              if not has_role(member, rolename_giveaway):
                members.append(member)
          if qty <= len(members):
            # print(f'entry role: {rolename_entry}\ngiveaway role: {rolename_giveaway}\nqty: {qty}')
            print(f'# of members with {rolename_entry} role: {len(members)}')
            winners = random.sample(members, qty)
            winner_str = ":tada: **Congratulations to the winners!** :tada:\n"
            for member in winners:
              await member.add_roles(role_giveaway)
              winner_str += ping_user_str(member.id)
            await ctx.channel.send(f'Members of **{rolename_entry}** without **{rolename_giveaway}** role: {len(members)}\n\n{winner_str}')
          else:
            message = f'# of winners cannot exceed amount of members in entry role: **{rolename_entry}** without the giveaway role: **{rolename_giveaway}**\nPossible winners: {len(members)} < specified winners: {qty}'
            await ctx.channel.send(message)
    else:
      message = f'# of winners must be greater than 0!'
      await ctx.channel.send(message)
  else:
    try:
      await ctx.author.send(message)
    except nextcord.Forbidden:
      pass

# RANDOM WL GIVEAWAY ERROR HANDLING #
@wlrand.error
async def wlrand_error(ctx, error):
  if isinstance(error, commands.BadArgument):
    if len(ctx.args) == 3:
      await ctx.channel.send(f'Invalid value passed to giveaway quantity')
    elif len(ctx.args) == 2:
      await ctx.channel.send(f'Invalid giveaway role entered')
    elif len(ctx.args) == 1:
      await ctx.channel.send(f'Invalid required role entered')
    else:
      await ctx.channel.send(f'an error has occurred')

# WHITELIST INFORMATION COMMAND #
@bot.command()
async def WL(ctx):
  message=wl_sorry(ctx.author.name)
  wl_role_name = await get_wl_role_name(ctx.guild)
  if has_role(ctx.author, wl_role_name):
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

# ROLE CHECK COMMAND #
@bot.command()
async def rolecheck(ctx, *, role_name=""):
  global rolemembers
  if is_admin(ctx.author.id):
    update_db()
    if role_name == "":
      role_name = await get_wl_role_name(ctx.guild)
    rolemembers = []
    newmembers = {}
    retiredmembers = {}
    print(f'searching for role: {role_name}')
    for member in ctx.guild.members:
      # print(f'Checking if {member.name} belongs to {role} role')
      for r in member.roles:
          if r.name == role_name:
            # names[str(member.id)] = member.name
            rolemembers.append(member.id)
            if not (member.id in names):
              # print(f'{member.id}: {member} is a new role member')
              newmembers[member.id] = member
    for k in names:
      # print(f'role checking id: {k}')
      if not (k in rolemembers):
        if k <= 999999999999999999:
          print(f'{k}: {names[k]} has been retired')
          retiredmembers[k] = names[k]
    # print(f'Members in {role} role:\n{rolemembers}')
    count_roles = len(rolemembers)
    count_names = len(names.keys())
    await ctx.channel.send(f'Members in WL DB: {count_names} | Members with {role_name} role: {count_roles}')
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

# BOT ON READY #
@bot.event
async def on_ready():
  print("The bot is now ready for use! Updating DBs")
  update_db()

# RUN THE BOT #
bot.run(TOKEN)

# @bot.slash_command(name="listdualwl", description="remove old WL role from members with both roles",guild_ids=guilds)
# async def list_dual_roles(interaction: Interaction):
#   role1 = "Hedgies WL"
#   role2 = "Hedgies WL (CRO)"
#   message = 'getting dual roles...'
#   if is_admin(interaction.user.id):
#     dual_roles = {}
#     for member in interaction.guild.members:
#       member_id = member.id
#       roles = {"role1": False, "role2": False}
#       for r in member.roles:
#         if r.name == role1:
#           roles["role1"] = True
#         if r.name == role2:
#           roles["role2"] = True
#       if roles["role1"] and roles["role2"]:
#         dual_roles[member.id] = member.name
#     user_str = condensed_users_str(dual_roles)
#     msg_count = f'# of members with both roles: {len(dual_roles.keys())}\n'
#     msg_combined = f'{msg_count}{user_str}'
#     if len(msg_combined) <= 2000:
#       message = msg_combined
#     else:
#       message = '# of users with both roles exceeds discord character limit, check logs.'
#       print(f'{msg_combined}')
#   else:
#     message = f'{interaction.user.name}, you are not authorized to use this command!'
#   await interaction.response.send_message(message)

# @bot.slash_command(name="purgedualwl", description="remove old WL role from members with both roles",guild_ids=guilds)
# async def purge_dual_roles(interaction: Interaction):
#   role1 = "Hedgies WL"
#   role2 = "Hedgies WL (CRO)"
#   message = f'{interaction.user.name}, you are not authorized to use this command!'
#   if is_admin(interaction.user.id):
#     dual_roles = {}
#     for member in interaction.guild.members:
#       member_id = member.id
#       roles = {"role1": False, "role2": False}
#       for r in member.roles:
#         if r.name == role1:
#           roles["role1"] = True
#         if r.name == role2:
#           roles["role2"] = True
#       if roles["role1"] and roles["role2"]:
#         dual_roles[member.id] = member.name
#         #remove role 1
#         role = nextcord.utils.get(interaction.guild.roles, name=role1)
#         try:
#           await member.remove_roles(role)
#         except nextcord.Forbidden:
#           pass
#     user_str = condensed_users_str(dual_roles)
#     message = f'Removing {role1} from {len(dual_roles.keys())} users.\n'
#     if len(message + user_str) <= 2000:
#       message += user_str
#     else:
#       message = '# of users with both roles exceeds discord character limit, check logs.'
#       print(f'{message}{user_str}')
#   await interaction.response.send_message(message)