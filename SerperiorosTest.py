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
from Misc import listToString as lts, singularOrPluralFromList as sopL, addDays, addMinutes
import threading
from datetime import datetime
from dotenv import load_dotenv
from catbox_api import catboxAPI

updateDBLock = threading.Lock()

channelIDs = {'prompts':1249849815886725130,'technicals':1249849864729395241,
              'voting':1249849883569946655,'results':1249849942928003164,
              'log':1249886965046706206}
roleIDs = {'prize':1263736029131706378,'alive':1263724263807127595,'eliminated':1263724948682444861}
serverID = 1204238093062901821

intents = discord.Intents.default() #Defining intents
intents.message_content = True # Adding the message_content intent so that the bot can read user messages
intents.members = True

load_dotenv()
bot = commands.Bot(command_prefix='sp/',owner_id=82629898316808192,intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")
    try:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        period = seasonInfoDB['period']
        deadline = seasonInfoDB['deadline']
        enforceDeadline = seasonInfoDB['enforceDeadline']
        if deadline and period in ('responding','voting') and enforceDeadline:
            await executeDeadline()
    except:
        pass

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
    with updateDBLock:
        message, channelName = func()
    if channelName:
        channel = bot.get_channel(channelIDs[channelName])
        await channel.send(message)
    else:
        owner = await bot.fetch_user(82629898316808192)
        await owner.send(message)

async def doTaskSendMessageAndReturnExtras(func):
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

async def removeRoleFromList(roleID,memberList:list[discord.Member]):
    role = await getRole(roleID)
    for member in memberList:
        if role in member.roles:
            await member.remove_roles(role)

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startSeason(ctx):
    SeasonInfo.createSeasonInfoDB()
    server: discord.Guild = bot.get_guild(serverID)
    userList = server.members
    print(userList)
    for roleType in roleIDs:
        await removeRoleFromList(roleIDs[roleType],userList)
    await ctx.send(f"Success! {SeasonInfo.seasonName} has started!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def setLimit(ctx,num,type):
    if not num.isnumeric():
        await ctx.send(f"Error! {num} is not a number!")
        return
    if type not in ("word","char"):
        await ctx.send(f"Error! {type} is not a valid limit type!")
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        seasonInfoDB['limit'] = int(num)
        seasonInfoDB['limitType'] = type
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    await ctx.send(f"Success! The limit is now {num} {type}s!")

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
        botMessage = f"Update: The {period} deadline is now"
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
        DNPList = await doTaskSendMessageAndReturnExtras(RespondingPeriod.closeResponding)
        await removeRoleFromList(DNPList)
        await doTaskAndSendMessage(VotingPeriod.startVoting)
        await executeDeadline()
    if period == 'voting':
        await doTaskAndSendMessage(VotingPeriod.closeVoting)
        return

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startResponding(ctx,*,prompt):
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        period = seasonInfoDB['period']
        if period != 'preResponding':
            await ctx.send(f"Error! Current period is {period}!")
            return
        currentRound = seasonInfoDB['currentRound']
        RespondingPeriod.createResponseDB()
        if len(seasonInfoDB['prompts'])<currentRound:
            seasonInfoDB['prompts'].append(prompt)
        else:
            seasonInfoDB['prompts'][currentRound-1]=prompt
        seasonInfoDB['period'] = 'responding'
        channel = bot.get_channel(channelIDs['prompts'])
        botMessage = (f"Round {str(currentRound)} has started! Your prompt is: \n"+
                        f"```{prompt}```")
        limitType = {'char':'characters','word':'words'}[seasonInfoDB['limitType']]
        limit = str(seasonInfoDB['limit'])
        botMessage += f"Your response must not exceed **{limit} {limitType}**, or it will be rejected."
        deadline = None
        if seasonInfoDB['deadlineMode']=='min':
            deadline = addMinutes(datetime.now().timestamp(),seasonInfoDB['deadlineLen'])
            botMessage += f'\nRespond by <t:{deadline}:T>, which is <t:{deadline}:R>.'
        elif seasonInfoDB['deadlineMode']=='day':
            deadline = addDays(datetime.now().timestamp(),seasonInfoDB['deadlineLen'])
            botMessage += f'\nRespond by <t:{deadline}:F>, which is <t:{deadline}:R>.'
        seasonInfoDB['deadline'] = deadline
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
        await channel.send(botMessage)
        await ctx.send(f"Success! Responding period has started!")
    if deadline and seasonInfoDB['enforceDeadline']:
        await executeDeadline()

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def closeResponding(ctx):
    DNPList = await doTaskSendMessageAndReturnExtras(RespondingPeriod.closeResponding)
    await removeRoleFromList(DNPList)


@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startVoting(ctx):
    await doTaskAndSendMessage(VotingPeriod.startVoting)
    enforceDeadline = SeasonInfo.getSeasonInfoDB()['enforceDeadline']
    if enforceDeadline:
        await executeDeadline()
    
@bot.command()
@commands.is_owner()
@commands.dm_only()
async def closeVoting(ctx):
    await doTaskAndSendMessage(VotingPeriod.closeVoting)
    

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def prelimResults(ctx):
    _,_,sheetID = CalculateResults.generateResults()
    await ctx.send(f"https://docs.google.com/spreadsheets/d/{sheetID}")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def applyResults(ctx):
    await ctx.send('Are you SURE you want to apply results? Reply "yes" within 10 seconds if so.')
    reply = await getConfirmationMessage(ctx)
    if not reply or reply.lower() != "yes":
        await ctx.send("Results will not be applied.")
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period !='results':
        await ctx.send(f"Error! Current period is {period}!")
        return
    _, contestantScorePairs, _ = CalculateResults.generateResults(getSheet=False)
    prizerIDs, elimIDs = CalculateResults.awardElimsAndPrizes(contestantScorePairs)
    server: discord.Guild = bot.get_guild(serverID)
    prizerMembers = [server.get_member(userID) for userID in prizerIDs]
    await addRoleToList(roleIDs['prize'],prizerMembers)
    elimMembers = [server.get_member(userID) for userID in elimIDs]
    await removeRoleFromList(roleIDs['eliminated',elimMembers])
    prizerNames = SeasonInfo.getDisplayNamesFromIDs(prizerIDs)
    elimNames = SeasonInfo.getDisplayNamesFromIDs(elimIDs)
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    with updateDBLock:
        seasonInfoDB['period'] = 'preResponding'
        seasonInfoDB['currentRound'] += 1
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    channel = bot.get_channel(channelIDs['results'])
    await channel.send(f"Results have been applied!")
    if len(seasonInfoDB['aliveContestants'])!=1:
        await channel.send(sopL(f"{lts(prizerNames)} {{has/have}} earned a prize."))
        await channel.send(sopL(f"{lts(elimNames)} {{has/have}} been eliminated."))
    else:
        seasonName = seasonInfoDB['seasonName']
        await channel.send(sopL(f"{lts(prizerNames)} is the winner of {seasonName}! Hooray!"))
        with updateDBLock:
            seasonInfoDB['period'] = 'over'
            SeasonInfo.updateSeasonInfoDB(seasonInfoDB)


@bot.command()
@commands.is_owner()
@commands.dm_only()
async def updateDisplayNames(ctx):
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        for userID in seasonInfoDB['aliveContestants']:
            user = await bot.fetch_user(int(userID))
            seasonInfoDB['aliveContestants'][userID]['displayName'] = user.display_name
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)

@bot.command()
@commands.dm_only()
async def respond(ctx,*,response):
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        if seasonInfoDB['period']!='responding':
            await ctx.send('Error! Responding is not currently open!')
            return
        currentRound = seasonInfoDB['currentRound']
        aliveContestants = seasonInfoDB['aliveContestants']
        userID = str(ctx.message.author.id)
        messageID = str(ctx.message.id)
        print('ok')
        # check if the user is alive
        # if not, add them to the pool if it's r1, but reject their response if it's after r1
        dbNeedsUpdating = False
        if userID not in aliveContestants:
            if currentRound != 1:
                await ctx.send('Error! You are not currently a contestant!')
                return
            else:
                user = await bot.fetch_user(int(userID))
                seasonInfoDB['aliveContestants'][userID] = {}
                seasonInfoDB['aliveContestants'][userID]['displayName'] = user.display_name
                dbNeedsUpdating = True
        botMessage = RespondingPeriod.addResponse(userID,response,messageID)
        await ctx.send(botMessage)
        print(ctx.message.id)
        if botMessage[0]=='S':
            if dbNeedsUpdating:
                await user.add_roles(getRole(roleIDs['alive']))
                SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
            channel = bot.get_channel(channelIDs['log'])
            user = await bot.fetch_user(int(userID))
            username = user.name
            await channel.send(f'{username} has responded: `{response}`')
    
@bot.command()
@commands.dm_only()
async def edit(ctx,*,newResponse):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='responding':
        await ctx.send('Error! Responding is not currently open!')
        return
    aliveContestants = seasonInfoDB['aliveContestants']
    userID = str(ctx.message.author.id)
    messageID = str(ctx.message.id)
    # check if the user is alive
    # if not, reject their edit
    if userID not in aliveContestants:
        await ctx.send('Error! You are not an alive contestant!')
        return
    # check if they included a number for which response to edit
    splitAtFirstSpace = newResponse.split(' ',1)
    if splitAtFirstSpace[0].isnumeric():
        number = int(splitAtFirstSpace[0])
        newResponse = splitAtFirstSpace[1]
    else:
        number = 1
    botMessage = RespondingPeriod.editResponse(userID,number,newResponse,messageID)
    await ctx.send(botMessage)
    print(ctx.message.id)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        user = await bot.fetch_user(int(userID))
        username = user.name
        await channel.send(f'{username} has edited their response: `{newResponse}`')

@bot.command()
@commands.dm_only()
async def setbook(ctx):
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

# TODO: add case insensitivity for small screens
@bot.command()
@commands.dm_only()
async def vote(ctx,keyword,letters):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        await ctx.send('Error! Voting is not currently open!')
        return
    userID = str(ctx.message.author.id)
    botMessage = VotingPeriod.addVote(userID,keyword,letters)
    await ctx.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        user = await bot.fetch_user(int(userID))
        username = user.name
        if "edited" in botMessage:
            await channel.send(f'{username} has edited their vote: `{keyword} {letters}`')
        else:
            await channel.send(f'{username} has sent a vote: `{keyword} {letters}`')

@bot.command()
@commands.dm_only()
async def editvote(ctx,keyword,letters):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        await ctx.send('Error! Voting is not currently open!')
        return
    userID = str(ctx.message.author.id)
    botMessage = VotingPeriod.editVote(userID,keyword,letters)
    await ctx.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        user = await bot.fetch_user(int(userID))
        username = user.name
        await channel.send(f'{username} has edited a vote: `{keyword} {letters}`')

@bot.command()
@commands.dm_only()
async def deletevote(ctx,keyword):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        await ctx.send('Error! Voting is not currently open!')
        return
    userID = str(ctx.message.author.id)
    botMessage = VotingPeriod.deleteVote(userID,keyword)
    await ctx.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        user = await bot.fetch_user(int(userID))
        username = user.name
        await channel.send(f'{username} has deleted their vote on screen `{keyword}`')

@bot.command()
@commands.dm_only()
async def clearvotes(ctx):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='voting':
        await ctx.send('Error! Voting is not currently open!')
        return
    userID = str(ctx.message.author.id)
    botMessage = VotingPeriod.clearVotes(userID)
    await ctx.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        user = await bot.fetch_user(int(userID))
        username = user.name
        await channel.send(f'{username} has cleared all their votes')

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

@startSeason.error
@setLimit.error
@setDeadline.error
@enforceDeadline.error
@allowGrace.error
@startResponding.error
@closeResponding.error
@startVoting.error
@closeVoting.error
@prelimResults.error
@applyResults.error
@updateDisplayNames.error
async def hostCommandError(ctx,error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Error! Required argument missing!")
    else:
        print(error)
        await ctx.send(f"Something is wrong. Please report this error to SergeantSnivy.")

bot.run(os.getenv('BOT_TOKEN')) # run the bot with the token


