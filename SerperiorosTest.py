import discord
import random
import asyncio
from discord.ext import commands
import os
import RespondingPeriod
import GenerateVoting
import VotingPeriod
import CalculateResults
import SeasonInfo
from PrivateStuff import pathToBot
from Stats import updateAllStats, removeMostRecentRoundFromAllStats
from Stats import addLeaderboardToSheet, removeMostRecentLeaderboardFromSheet
from Misc import listToString as lts, singularOrPluralFromList as sopL, addDays, addMinutes
import threading
from datetime import datetime
from dotenv import load_dotenv
from catbox_api import catboxAPI

updateDBLock = threading.Lock()

channelIDs = {'prompts':1249849815886725130,'technicals':1249849864729395241,
              'voting':1249849883569946655,'results':1249849942928003164,
              'log':1249886965046706206,'supervoterTalk':1280703395690451006}
roleIDs = {'prize':1263736029131706378,'alive':1263724263807127595,'eliminated':1263724948682444861,
           'supervoter':1280703462631276594,'supervoterReviews':1287186738975997954,'noreminders':1287181190432034886}
serverID = 1204238093062901821

intents = discord.Intents.default() #Defining intents
intents.message_content = True # Adding the message_content intent so that the bot can read user messages
intents.members = True

load_dotenv()
bot = commands.Bot(command_prefix='sp/',owner_id=82629898316808192,intents=intents)

@bot.event
async def on_ready():
    owner = await bot.fetch_user(82629898316808192)
    await owner.send("I'm online!")
    print(f"{bot.user} is ready and online!")
    # get season name so it knows which directory to enter
    os.chdir(pathToBot)
    try:
        os.mkdir("metaInfo")
    except:
        pass
    os.chdir("metaInfo")
    with open('currentSeasonName.txt','r') as f:
        seasonName = f.read()
    os.chdir(pathToBot)
    print(os.getcwd())
    os.chdir(seasonName)
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    deadline = seasonInfoDB['deadline']
    enforceDeadline = seasonInfoDB['enforceDeadline']
    if deadline and period in ('responding','voting') and enforceDeadline:
        await executeDeadline()

async def getConfirmationMessage(ctx):
    def check(message):
        return message.author == ctx.author and message.channel == ctx.channel
    try:
        message = await bot.wait_for('message', timeout=10.0, check=check)
    except asyncio.TimeoutError:
        return None
    else:
        return message.content

async def doTaskAndSendMessage(func):
    print("Performing "+func.__name__)
    with updateDBLock:
        message, channelName = func()
    if channelName:
        channel = bot.get_channel(channelIDs[channelName])
        await channel.send(message)
    else:
        owner = await bot.fetch_user(82629898316808192)
        await owner.send(message)

async def doTaskSendMessageAndReturnExtras(func):
    print("Performing "+func.__name__)
    with updateDBLock:
        message, channelName, extras = func()
    if channelName:
        channel = bot.get_channel(channelIDs[channelName])
        await channel.send(message)
    else:
        owner = await bot.fetch_user(82629898316808192)
        await owner.send(message)
    return extras

async def getRole(roleID):
    print('ok')
    role = bot.get_guild(serverID).get_role(roleID)
    print(role)
    return role

async def addRoleToList(roleID,memberList:list[discord.Member]):
    role = await getRole(roleID)
    for member in memberList:
        if role not in member.roles:
            await member.add_roles(role)

async def checkIfUserHasRole(roleID,member:discord.Member):
    role = await getRole(roleID)
    return role in member.roles

async def removeRoleFromList(roleID,memberList:list[discord.Member]):
    role = await getRole(roleID)
    for member in memberList:
        if role in member.roles:
            await member.remove_roles(role)

async def removeNoReminders():
    server: discord.Guild = bot.get_guild(serverID)
    userList = server.members
    await removeRoleFromList(roleIDs['noreminders'],userList)

async def removeSupervoter():
    server: discord.Guild = bot.get_guild(serverID)
    userList = server.members
    await removeRoleFromList(roleIDs['supervoter'],userList)

async def removeSupervoterReviews():
    server: discord.Guild = bot.get_guild(serverID)
    userList = server.members
    await removeRoleFromList(roleIDs['supervoterReviews'],userList)

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def removeAllTWOWRoles(ctx):
    server: discord.Guild = bot.get_guild(serverID)
    userList = server.members
    print(userList)
    for roleType in roleIDs:
        await removeRoleFromList(roleIDs[roleType],userList)

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startSeason(ctx,seasonName):
    SeasonInfo.createSeasonInfoDB(seasonName)
    await removeAllTWOWRoles(ctx)
    await ctx.send(f"Success! {seasonName} has started!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def setLimit(ctx,num,type):
    if not num.isnumeric():
        await ctx.send(f"Error! {num} is not a number!")
        return
    if type not in ("word","char"):
        await ctx.send(f"Error! {type} is not a valid limit type!")
    print("Setting limit")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        seasonInfoDB['limit'] = int(num)
        seasonInfoDB['limitType'] = type
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    await ctx.send(f"Success! The limit is now {num} {type}s!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def setPeriod(ctx,newPeriod):
    if newPeriod not in ['preResponding','responding','preVoting','voting','results','over']:
        await ctx.send(f"Error! {newPeriod} is not a valid period!")
        return
    currentPeriod = SeasonInfo.getSeasonInfoDB()['period']
    if newPeriod==currentPeriod:
        await ctx.send(f"Error! {newPeriod} is already the current period!")
    print("Setting period")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        seasonInfoDB['period'] = newPeriod
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    await ctx.send(f"Success! The period is now {newPeriod}!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def setDeadline(ctx,timestamp):
    if not timestamp.isnumeric():
        await ctx.send("Error! Invalid timestamp!")
        return
    # make sure that's not already the deadline
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if timestamp==seasonInfoDB['deadline']:
        await ctx.send("Error! That's already the deadline!")
        return
    print("Setting deadline")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        print(seasonInfoDB)
        seasonInfoDB['deadline'] = int(timestamp)
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    period = seasonInfoDB['period']
    channel = None
    if period=='responding':
        channel = bot.get_channel(channelIDs['prompts'])
    elif period=='voting':
        channel = bot.get_channel(channelIDs['voting'])
    if channel:
        botMessage = f"Update: The {period} deadline is now "
        if seasonInfoDB['deadlineMode']=='min':
            botMessage += f'<t:{timestamp}:T>, which is <t:{timestamp}:R>!'
        elif seasonInfoDB['deadlineMode']=='day':
            botMessage += f'<t:{timestamp}:F>, which is <t:{timestamp}:R>!'
        await channel.send(botMessage)
    await ctx.send(f"Success! The deadline is now <t:{timestamp}:F>, which is <t:{timestamp}:R>!")
    await executeDeadline()

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def enforceDeadline(ctx):
    print("Attempting to enforce deadline")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        if not seasonInfoDB['deadline']:
            await ctx.send("Error! You have not set a deadline!")
            return
        if seasonInfoDB['enforceDeadline']:
            await ctx.send("The deadline is already being enforced.")
            return
        seasonInfoDB['enforceDeadline'] = True
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
        await ctx.send("Success! You are now enforcing the deadline!")
    period = seasonInfoDB['period']
    channel = None
    if period=='responding':
        channel = bot.get_channel(channelIDs['prompts'])
    elif period=='voting':
        channel = bot.get_channel(channelIDs['voting'])
    if channel:
        botMessage = f"Update: The {period} deadline will be strictly enforced!"
        if seasonInfoDB['deadlineMode']=='min':
            deadline = addMinutes(datetime.now().timestamp(),seasonInfoDB['deadlineLen'])
            botMessage += f'\nRemember, the deadline is <t:{deadline}:T>, which is <t:{deadline}:R>.'
        elif seasonInfoDB['deadlineMode']=='day':
            deadline = addDays(datetime.now().timestamp(),seasonInfoDB['deadlineLen'])
            botMessage += f'\nRemember, the deadline is <t:{deadline}:F>, which is <t:{deadline}:R>.'
    await executeDeadline()

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def allowGrace(ctx):
    print("Attempting to allow grace")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        if not seasonInfoDB['enforceDeadline']:
            await ctx.send("You are already allowing grace.")
            return
        seasonInfoDB['enforceDeadline'] = False
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
        await ctx.send("Success! You are now allowing grace!")

async def executeDeadline():
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    print(period)
    if period not in ['responding','voting']:
        return f"Current period is {period} when it should be responding or voting. Something is wrong!"
    deadline = seasonInfoDB['deadline']
    print("OK")
    waitTime = deadline - datetime.now().timestamp()
    print(waitTime)
    print("SSHIGFSHAFI")
    if waitTime <= 0:
        return f"Deadline has already passed. Something is wrong!"
    await asyncio.sleep(waitTime)
    # make sure I haven't allowed grace; if I have, cancel
    print("Deadline up")
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    enforceDeadline = seasonInfoDB['enforceDeadline']
    if not enforceDeadline:
        return
    # make sure I haven't changed the deadline or period; if I have, cancel
    potentialNewDeadline = seasonInfoDB['deadline']
    potentialNewPeriod = seasonInfoDB['period']
    if deadline != potentialNewDeadline or period != potentialNewPeriod:
        return
    # now we're good to execute
    if period == 'responding':
        print('responding')
        DNPList = await doTaskSendMessageAndReturnExtras(RespondingPeriod.closeResponding)
        if seasonInfoDB['elimFormat'] == 'rollingAverage':
            server: discord.Guild = bot.get_guild(serverID)
            DNPMembers = [await server.fetch_member(userID) for userID in DNPList]
            await removeRoleFromList(roleIDs['alive'],DNPMembers)
            await addRoleToList(roleIDs['eliminated'],DNPMembers)
        await doTaskAndSendMessage(VotingPeriod.startVoting)
        await executeDeadline()
    if period == 'voting':
        print('voting')
        await doTaskAndSendMessage(VotingPeriod.closeVoting)
        return

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startResponding(ctx,*,prompt):
    print("Attempting to start responding")
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period != 'preResponding':
        await ctx.send(f"Error! Current period is {period}!")
        return
    limitType = seasonInfoDB['limitType']
    limitNum = str(seasonInfoDB['limit'])
    await ctx.send(f'The prompt will be as follows:\n`{prompt}`\n'+
                   f'The limit is currently {limitNum} {limitType}s.\n'+
                   'Is this correct? Reply "yes" within 10 seconds if so.')
    reply = await getConfirmationMessage(ctx)
    if not reply or reply.lower() != "yes":
        await ctx.send("The prompt was not sent.")
        return
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        currentRound = seasonInfoDB['currentRound']
        # failsafe against starting responding twice for some reason
        if len(seasonInfoDB['prompts'])<currentRound:
            seasonInfoDB['prompts'].append(prompt)
        else:
            seasonInfoDB['prompts'][currentRound-1]=prompt
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    await doTaskAndSendMessage(RespondingPeriod.startResponding)
    await ctx.send("Success! Responding has started!")
    enforceDeadline = SeasonInfo.getSeasonInfoDB()['enforceDeadline']
    if enforceDeadline:
        await executeDeadline()

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def closeResponding(ctx):
    DNPList = await doTaskSendMessageAndReturnExtras(RespondingPeriod.closeResponding)
    await ctx.send("Success! Responding is closed!")
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if DNPList and seasonInfoDB['elimFormat'] == 'vanilla':
        server: discord.Guild = bot.get_guild(serverID)
        DNPMembers = [await server.fetch_member(userID) for userID in DNPList]
        await removeRoleFromList(roleIDs['alive'],DNPMembers)
        await addRoleToList(roleIDs['eliminated'],DNPMembers)
    await removeNoReminders()


@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startVoting(ctx):
    await doTaskAndSendMessage(VotingPeriod.startVoting)
    await ctx.send("Success! Voting has started!")
    enforceDeadline = SeasonInfo.getSeasonInfoDB()['enforceDeadline']
    if enforceDeadline:
        await executeDeadline()
    
@bot.command()
@commands.is_owner()
@commands.dm_only()
async def closeVoting(ctx):
    await doTaskAndSendMessage(VotingPeriod.closeVoting)
    await ctx.send("Success! Voting is closed!")
    

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def prelimResults(ctx):
    _,contestantScorePairs,_,sheetID = CalculateResults.generateResults()
    await ctx.send(f"https://docs.google.com/spreadsheets/d/{sheetID}")
    if SeasonInfo.getSeasonInfoDB()['elimFormat']=='rollingAverage':
        _,_,_,sheetID = CalculateResults.generatePhaseResults(contestantScorePairs)
        await ctx.send(f"https://docs.google.com/spreadsheets/d/{sheetID}")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def applyResults(ctx):
    await ctx.send('Are you SURE you want to apply results? Reply "yes" within 10 seconds if so.')
    reply = await getConfirmationMessage(ctx)
    if not reply or reply.lower() != "yes":
        await ctx.send("Results will not be applied.")
        return
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period !='results':
        await ctx.send(f"Error! Current period is {period}!")
        return
    # set backup
    SeasonInfo.updateSeasonInfoBackupDB(seasonInfoDB)
    _, contestantScorePairs, statsRows, resultsSheetID = CalculateResults.generateResults(getSheet=True)
    oldPrizerIDs = seasonInfoDB['currentPrizers']
    statsSheetID = updateAllStats(statsRows)
    addLeaderboardToSheet(resultsSheetID)
    # note: awardElimsAndPrizes already recalculates elims based on rolling average if applicable
    prizerIDs, elimIDs = CalculateResults.awardElimsAndPrizes(contestantScorePairs)
    print(prizerIDs)
    print(elimIDs)
    server: discord.Guild = bot.get_guild(serverID)
    oldPrizerMembers = [await server.fetch_member(userID) for userID in oldPrizerIDs]
    await removeRoleFromList(roleIDs['prize'],oldPrizerMembers)
    prizerMembers = [await server.fetch_member(userID) for userID in prizerIDs]
    print('1')
    await addRoleToList(roleIDs['prize'],prizerMembers)
    elimMembers = [await server.fetch_member(userID) for userID in elimIDs]
    await removeRoleFromList(roleIDs['alive'],elimMembers)
    await addRoleToList(roleIDs['eliminated'],elimMembers)
    prizerNames = SeasonInfo.getDisplayNamesFromIDs(prizerIDs,True)
    elimNames = SeasonInfo.getDisplayNamesFromIDs(elimIDs,False)
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    print('Incrementing current round')
    with updateDBLock:
        seasonInfoDB['period'] = 'preResponding'
        seasonInfoDB['currentRound'] += 1
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    channel = bot.get_channel(channelIDs['results'])
    await channel.send(f"Results have been applied!")
    if len(seasonInfoDB['aliveContestants'])!=1:
        await channel.send(sopL(f"{lts(prizerNames)} {{has/have}} earned a prize."))
        if len(elimNames)!=0:
            await channel.send(sopL(f"{lts(elimNames)} {{has/have}} been eliminated."))
        else:
            await channel.send("This round has no eliminations.")
    else:
        seasonName = seasonInfoDB['seasonName']
        await channel.send(sopL(f"{lts(prizerNames)} is the winner of {seasonName}! Hooray!"))
        print("Ending season")
        with updateDBLock:
            seasonInfoDB['period'] = 'over'
            SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    await channel.send(f"Stats sheet: \nhttps://docs.google.com/spreadsheets/d/{statsSheetID}")
    await ctx.send("Success! Results have been applied!")
    await removeNoReminders()
    await removeSupervoter()
    await removeSupervoterReviews()

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def undoResults(ctx):
    await ctx.send('Are you SURE you want to UNDO results? Reply "yes" within 10 seconds if so.')
    reply = await getConfirmationMessage(ctx)
    if not reply or reply.lower() != "yes":
        await ctx.send("Results will not be applied.")
        return
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period !='preResponding':
        await ctx.send(f"Error! Current period is {period}!")
        return
    # load backup
    seasonInfoBackupDB = SeasonInfo.getSeasonInfoBackupDB()
    seasonInfoBackupDB['statsSheetID'] = seasonInfoDB['statsSheetID']
    prizerIDsToUndo = seasonInfoDB['currentPrizers']
    prizerIDsToRestore = seasonInfoBackupDB['currentPrizers']
    elimIDsToUndo = set(seasonInfoDB['eliminatedContestants']).intersection(set(seasonInfoBackupDB['aliveContestants']))
    server: discord.Guild = bot.get_guild(serverID)
    prizerMembersToUndo = [await server.fetch_member(userID) for userID in prizerIDsToUndo]
    await removeRoleFromList(roleIDs['prize'],prizerMembersToUndo)
    prizerMembersToRestore = [await server.fetch_member(userID) for userID in prizerIDsToRestore]
    await addRoleToList(roleIDs['prize'],prizerMembersToRestore)
    elimMembersToUndo = [await server.fetch_member(userID) for userID in elimIDsToUndo]
    await removeRoleFromList(roleIDs['eliminated'],elimMembersToUndo)
    await addRoleToList(roleIDs['alive'],elimMembersToUndo)
    # overwrite DB with backup
    with updateDBLock:
        SeasonInfo.updateSeasonInfoDB(seasonInfoBackupDB)
    # undo stats
    statsSheetID = removeMostRecentRoundFromAllStats()
    removeMostRecentLeaderboardFromSheet()
    channel = bot.get_channel(channelIDs['results'])
    await channel.send(f"Results have been undone.")
    #await channel.send(f"Stats sheet: \nhttps://docs.google.com/spreadsheets/d/{statsSheetID}")
    await ctx.send("Success! Results have been undone!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def updateDisplayNames(ctx):
    print("Updating display names")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        for userID in seasonInfoDB['aliveContestants']:
            user = await bot.fetch_user(int(userID))
            seasonInfoDB['aliveContestants'][userID]['displayName'] = user.display_name
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def forceEliminate(ctx,contestantID):
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB
        if contestantID not in seasonInfoDB['aliveContestants']:
            await ctx.send("Error! That user is not an alive contestant!")
            return
        contestantDict = seasonInfoDB['aliveContestants'][contestantID]
        del seasonInfoDB['aliveContestants'][contestantID]
        seasonInfoDB['eliminatedContestants'][contestantID] = contestantDict
        server: discord.Guild = bot.get_guild(serverID)
        userMemberInList = [await server.fetch_member(contestantID)]
        await addRoleToList(roleIDs['eliminated'],userMemberInList)
        await removeRoleFromList(roleIDs['alive'],contestantID)
        await ctx.send("Success! That contestant has been eliminated!")


@bot.command()
@commands.dm_only()
async def respond(ctx,*,response):
    userID = str(ctx.message.author.id)
    messageID = str(ctx.message.id)
    user = await bot.fetch_user(userID)
    await recordResponse(userID,messageID,user,response)

async def recordResponse(userID,messageID,user,response):
    print("Recording a response")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        if seasonInfoDB['period']!='responding':
            message = 'Error! Responding is not currently open!'
            await user.send(message)
            return message
        currentRound = seasonInfoDB['currentRound']
        aliveContestants = seasonInfoDB['aliveContestants']
        print('ok')
        # check if the user is alive
        # if not, add them to the pool if it's r1, but reject their response if it's after r1
        dbNeedsUpdating = False
        if userID not in aliveContestants:
            if currentRound != 1 and not (seasonInfoDB['elimFormat']=='rollingAverage' and currentRound==2):
                message = 'Error! You are not currently a contestant!'
                await user.send(message)
                return message
            else:
                user = await bot.fetch_user(int(userID))
                currentContestantDB = seasonInfoDB['aliveContestants'][userID] = {}
                currentContestantDB['displayName'] = user.display_name
                if seasonInfoDB['elimFormat']=='rollingAverage':
                    currentContestantDB['prevScore'] = 0
                dbNeedsUpdating = True
        botMessage = RespondingPeriod.addResponse(userID,response,messageID)
        await user.send(botMessage)
        if botMessage[0]=='S':
            if dbNeedsUpdating:
                server: discord.Guild = bot.get_guild(serverID)
                member = await server.fetch_member(userID) 
                await member.add_roles(await getRole(roleIDs['alive']))
                SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
            channel = bot.get_channel(channelIDs['log'])
            username = user.name
            number = len(RespondingPeriod.getResponseDB()[userID])
            await channel.send(f'{username} ({userID}) has responded [{str(number)}]: `{response}`')
        return botMessage

@bot.command(aliases=["editresponse"])
@commands.dm_only()
async def edit(ctx,*,newResponse):
    userID = str(ctx.message.author.id)
    messageID = str(ctx.message.id)
    user = await bot.fetch_user(userID)
    await recordResponseEdit(userID,messageID,user,newResponse)
    
async def recordResponseEdit(userID,messageID,user,newResponse):
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        if seasonInfoDB['period']!='responding':
            message = 'Error! Responding is not currently open!'
            await user.send(message)
            return message
        aliveContestants = seasonInfoDB['aliveContestants']
        # check if the user is alive
        # if not, reject their edit
        if userID not in aliveContestants:
            message = 'Error! You are not an alive contestant!'
            await user.send(message)
            return message
        # check if they included a number for which response to edit
        splitAtFirstSpace = newResponse.split(' ',1)
        if splitAtFirstSpace[0].isdigit():
            number = int(splitAtFirstSpace[0])
            newResponse = splitAtFirstSpace[1]
        else:
            number = 1
        botMessage = RespondingPeriod.editResponse(userID,number,newResponse,messageID)
        await user.send(botMessage)
        if botMessage[0]=='S':
            channel = bot.get_channel(channelIDs['log'])
            user = await bot.fetch_user(int(userID))
            username = user.name
            await channel.send(f'{username} ({userID}) has edited their response [{str(number)}]: `{newResponse}`')
        return botMessage

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def respondFor(ctx,userID,*,response):
    messageID = str(ctx.message.id)
    user = await bot.fetch_user(userID)
    await user.send("The host has sent a command for you. Result:")
    botMessage = await recordResponse(userID,messageID,user,response)
    username = user.name
    await ctx.send(f"Attempted to add response for {username}. Message returned:\n```{botMessage}```")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def rejectResponse(ctx,userID,responseNum: str,*,reason):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='responding':
        message = 'Error! Responding is not currently open!'
        return
    if not responseNum.isdigit():
        await ctx.send("Error: Invalid number!")
        return
    message,responseContent = RespondingPeriod.removeResponse(userID,int(responseNum))
    if message[0]=='S':
        user = await bot.fetch_user(userID)
        await user.send(f"Your response `{responseContent}` was rejected. Reason: `{reason}`")
    await ctx.send(message)

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def editFor(ctx,userID,*,newResponse):
    messageID = str(ctx.message.id)
    user = await bot.fetch_user(userID)
    await user.send("The host has sent a command for you. Result:")
    botMessage = await recordResponseEdit(userID,messageID,user,newResponse)
    username = user.name
    await ctx.send(f"Attempted to edit response for {username}. Message returned:\n```{botMessage}```")


@bot.command()
@commands.dm_only()
async def viewresponses(ctx):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='responding':
        await ctx.send('Error! Responding is not currently open!')
        return
    aliveContestants = seasonInfoDB['aliveContestants']
    userID = str(ctx.message.author.id)
    # check if the user is alive
    if userID not in aliveContestants:
        await ctx.send('Error! You are not an alive contestant!')
        return
    botMessage = RespondingPeriod.viewResponses(userID)
    await ctx.send(botMessage)

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def viewResponsesOf(ctx,userID):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='responding':
        await ctx.send('Error! Responding is not currently open!')
        return
    aliveContestants = seasonInfoDB['aliveContestants']
    # check if the user is alive
    if userID not in aliveContestants:
        await ctx.send('Error! That user is not an alive contestant!')
        return
    botMessage = RespondingPeriod.viewResponses(userID)
    await ctx.send(botMessage)


@bot.command(aliases=['book'])
@commands.dm_only()
async def setbook(ctx):
    print("Recording a book")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        userID = str(ctx.message.author.id)
        # only alive contestants can set books
        if userID not in seasonInfoDB['aliveContestants']:
            await ctx.send('Error! You are not an alive contestant!')
            return
        attachments = ctx.message.attachments
        if len(attachments)==0:
            await ctx.send("Error! You did not attach an image!")
            return
        file = attachments[0]
        if file.content_type.split('/')[0]=='image':
            api = catboxAPI(os.getenv('CATBOX_TOKEN'))
            catboxURL = "https://files.catbox.moe/"+api.upload_from_url(file.url)
            seasonInfoDB['aliveContestants'][userID]['bookLink'] = catboxURL
            SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
            await ctx.send("Success! Your book has been set to the image you sent!")
            channel = bot.get_channel(channelIDs['log'])
            user = await bot.fetch_user(int(userID))
            username = user.name
            await channel.send(f'{username} has edited their book: `{catboxURL}`')
        else:
            await ctx.send("Error! The attached file is not an image!")

@respond.error
@edit.error
async def responseError(ctx,error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Error! You didn't include a response!")
    else:
        print(error)
        await ctx.send("Something is wrong. Please report this to SergeantSnivy.")

@bot.command()
@commands.dm_only()
async def vote(ctx,keyword,letters):
    userID = str(ctx.message.author.id)
    user = await bot.fetch_user(userID)
    await recordVote(userID,user,keyword,letters)

async def recordVote(userID,user,keyword,letters):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        message = 'Error! Voting is not currently open!'
        await user.send(message)
        return message
    botMessage = VotingPeriod.addVote(userID,keyword,letters)
    await user.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        username = user.name
        if "edited" in botMessage:
            await channel.send(f'{username} has edited their vote: `{keyword} {letters}`')
        else:
            await channel.send(f'{username} has sent a vote: `{keyword} {letters}`')
    # give them the supervoter role if they are now a supervoter
    if "supervoter" in botMessage:
        server: discord.Guild = bot.get_guild(serverID)
        userMemberInList = [await server.fetch_member(userID)]
        await addRoleToList(roleIDs['supervoter'],userMemberInList)
    return botMessage

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def voteFor(ctx,userID,keyword,letters):
    user = await bot.fetch_user(userID)
    await user.send("The host has sent a command for you. Result:")
    botMessage = await recordVote(userID,user,keyword,letters)
    username = user.name
    await ctx.send(f"Attempted to add vote for {username}. Message returned:\n```{botMessage}```")

@bot.command()
@commands.dm_only()
async def editvote(ctx,keyword,letters):
    userID = str(ctx.message.author.id)
    user = await bot.fetch_user(userID)
    await recordVoteEdit(userID,user,keyword,letters)

async def recordVoteEdit(userID,user,keyword,letters):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        message = 'Error! Voting is not currently open!'
        await user.send('Error! Voting is not currently open!')
        return message
    botMessage = VotingPeriod.editVote(userID,keyword,letters)
    await user.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        username = user.name
        await channel.send(f'{username} has edited a vote: `{keyword} {letters}`')
    return botMessage

@bot.command()
@commands.dm_only()
async def deletevote(ctx,keyword):
    userID = str(ctx.message.author.id)
    user = await bot.fetch_user(userID)
    await recordVoteDelete(userID,user,keyword)   

async def recordVoteDelete(userID,user,keyword):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        message = 'Error! Voting is not currently open!'
        await user.send(message)
        return
    botMessage = VotingPeriod.deleteVote(userID,keyword)
    await user.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        username = user.name
        await channel.send(f'{username} has deleted their vote on screen `{keyword}`')
    # remove the supervoter role if they have it
    server: discord.Guild = bot.get_guild(serverID)
    userMemberInList = [await server.fetch_member(userID)]
    await removeRoleFromList(roleIDs['supervoter'],userMemberInList)
    return botMessage

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def deleteVoteFor(ctx,userID,keyword):
    user = await bot.fetch_user(userID)
    await user.send("The host has sent a command for you. Result:")
    botMessage = await recordVoteDelete(userID,user,keyword)
    username = user.name
    await ctx.send(f"Attempted to delete vote for {username}. Message returned:\n```{botMessage}```")

@bot.command()
@commands.dm_only()
async def clearvotes(ctx):
    userID = str(ctx.message.author.id)
    user = await bot.fetch_user(userID)
    await recordVoteClear(userID,user)  

async def recordVoteClear(userID,user):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        message = 'Error! Voting is not currently open!'
        await user.send(message)
        return message
    botMessage = VotingPeriod.clearVotes(userID)
    await user.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        username = user.name
        await channel.send(f'{username} has cleared all their votes')
    # remove the supervoter role if they have it
    server: discord.Guild = bot.get_guild(serverID)
    userMemberInList = [await server.fetch_member(userID)]
    await removeRoleFromList(roleIDs['supervoter'],userMemberInList)
    return botMessage

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def clearVotesFor(ctx,userID):
    user = await bot.fetch_user(userID)
    await user.send("The host has sent a command for you. Result:")
    botMessage = await recordVoteClear(userID,user)
    username = user.name
    await ctx.send(f"Attempted to clear votes for {username}. Message returned:\n```{botMessage}```")

@bot.command()
@commands.dm_only()
async def viewvotes(ctx):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        await ctx.send('Error! Voting is not currently open!')
        return
    userID = str(ctx.message.author.id)
    botMessage = VotingPeriod.viewVotes(userID)
    await ctx.send(botMessage)

@bot.command()
@commands.dm_only()
@commands.is_owner()
async def viewVotesOf(ctx,userID):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        await ctx.send('Error! Voting is not currently open!')
        return
    botMessage = VotingPeriod.viewVotes(userID)
    await ctx.send(botMessage)

@bot.command()
@commands.dm_only()
async def supervoter(ctx):
    userID = str(ctx.message.author.id)
    period = SeasonInfo.getSeasonInfoDB()['period']
    if period != 'voting':
        await ctx.send("Error! The current period is not voting!")
        return
    #hasSupervoted returns a message if the user has not supervoted
    message = VotingPeriod.hasSupervoted(userID)
    if message:
        await ctx.send(message)
        return
    server: discord.Guild = bot.get_guild(serverID)
    userMember = await server.fetch_member(userID)
    if await checkIfUserHasRole(roleIDs['supervoterReviews'],userMember):
        await ctx.send("Error! You already have the Supervoter role! This cannot be undone.")
        return
    await ctx.send("Are you SURE you want access to the Supervoter channel? **You will not be able to edit or delete votes afterwards.**\n"+
                   "Type `yes` within 10 seconds to be given access to the Supervoter channel.")
    reply = await getConfirmationMessage(ctx)
    if not reply or reply.lower() != "yes":
        await ctx.send("Interaction cancelled. You were not given access to the Supervoter channel.")
        return
    server: discord.Guild = bot.get_guild(serverID)
    userMemberInList = [userMember]
    await addRoleToList(roleIDs['supervoterReviews'],userMemberInList)
    with updateDBLock:
        votesDB = VotingPeriod.getVotesDB()
        votesDB[userID]['supervoterAccess'] = True
        VotingPeriod.updateVotesDB(votesDB)
    await ctx.send("Success! You are now in the Supervoter channel!")

@bot.command()
@commands.dm_only()
async def noreminders(ctx):
    userID = str(ctx.message.author.id)
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    giveWarning = False
    server: discord.Guild = bot.get_guild(serverID)
    userMember = await server.fetch_member(userID)
    if await checkIfUserHasRole(roleIDs['noreminders'],userMember):
        await ctx.send("Error! You already have the No Reminders role! To remove it, use `sp/reminders`.")
        return
    if period=='responding':
        responseDB = RespondingPeriod.getResponseDB()
        # if they're not a contestant, they don't get responding reminders anyways
        if userID not in responseDB:
            await ctx.send("Error! You are not currently an alive contestant!")
            return
        # give a warning if they haven't sent all their responses
        maxResponses = RespondingPeriod.maxResponses(userID)
        if len(responseDB[userID])<maxResponses:
            giveWarning = True
    elif period not in ['voting']:
        await ctx.send("Error! This isn't a period where you can get reminders!")
        return
    # warn them if they haven't sent everything they can send
    if giveWarning:
        await ctx.send("Are you SURE you want the No Reminders role? **You have not yet sent all your allotted responses.**\n"+
                   "Type `yes` within 10 seconds to be given the No Reminders role.")
        reply = await getConfirmationMessage(ctx)
        if not reply or reply.lower() != "yes":
            await ctx.send("Interaction cancelled. You will still receive reminders.")
            return
    userMemberInList = [userMember]
    await addRoleToList(roleIDs['noreminders'],userMemberInList)
    await ctx.send("Success! You are no longer receiving reminders for this period.")

@bot.command()
@commands.dm_only()
async def reminders(ctx):
    userID = str(ctx.message.author.id)
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    server: discord.Guild = bot.get_guild(serverID)
    userMember = await server.fetch_member(userID)
    if not await checkIfUserHasRole(roleIDs['noreminders'],userMember):
        await ctx.send("Error! You are already receiving reminders! To opt out of reminders, use `sp/noreminders`.")
        return
    if period not in ['responding','voting']:
        await ctx.send("Error! This isn't a period where you can get reminders!")
        return
    userMemberInList = [userMember]
    await removeRoleFromList(roleIDs['noreminders'],userMemberInList)
    await ctx.send("Success! You will receive reminders for this period again.")

@vote.error
@editvote.error
async def voteSendError(ctx,error):
    if isinstance(error, commands.MissingRequiredArgument):
        if error.param.name=='keyword':
            await ctx.send("Error! You didn't include a screen to vote on or letters for a vote!")
        elif error.param.name=='letters':
            await ctx.send("Error! After the screen name, please include letters for the vote!")
    else:
        print(error)
        await ctx.send(f"Something is wrong. Please report this error to SergeantSnivy.")

@deletevote.error
@clearvotes.error
async def voteDeleteError(ctx,error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Error! You didn't include a screen name to delete your vote from!")
    else:
        await ctx.send(f"Something is wrong. Please report this error to SergeantSnivy.")

'''@startSeason.error
@setLimit.error
@setDeadline.error
@enforceDeadline.error
@allowGrace.error
@startResponding.error
@closeResponding.error
@startVoting.error
@closeVoting.error
@prelimResults.error
#@applyResults.error
@updateDisplayNames.error'''
async def hostCommandError(ctx,error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Error! Required argument missing!")
    else:
        print(error)
        await ctx.send(f"Something is wrong. Please report this error to SergeantSnivy.")

bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token


