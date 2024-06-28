import discord
import random
from discord.ext import commands
import os
import RespondingPeriod
import GenerateVoting
import VotingPeriod
import CalculateResults
import SeasonInfo
from Misc import listToString as lts, singularOrPluralFromList as sopL
import threading
from dotenv import load_dotenv

updateDBLock = threading.Lock()

channelIDs = {'prompts':1249849815886725130,'technicals':1249849864729395241,
              'voting':1249849883569946655,'results':1249849942928003164,
              'log':1249886965046706206}

intents = discord.Intents.default() #Defining intents
intents.message_content = True # Adding the message_content intent so that the bot can read user messages

load_dotenv()
bot = commands.Bot(command_prefix='sp/',owner_id=82629898316808192,intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")


@bot.command()
async def hello(ctx):
    await ctx.send("Hey!")

@bot.command()
async def cointoss(ctx):
    if random.random()<0.5:
        await ctx.send("Heads")
    else:
        await ctx.send("Tails")

@bot.command()
async def randint(ctx,minimum,maximum):
    minimum,maximum = int(minimum),int(maximum)
    await ctx.send(random.randint(minimum,maximum))

@bot.command()
async def repeat(ctx,n,*,message):
    n = int(n)
    output = ''.join([message+' ']*n)
    await ctx.send(output)

@bot.command()
@commands.is_owner()
async def thingy(ctx):
    await ctx.send("You can use this command")

@bot.command()
@commands.dm_only()
async def thingy2(ctx):
    await ctx.send("This is in a DM")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startSeason(ctx):
    SeasonInfo.createSeasonInfoDB()
    await ctx.send(f"Success! {SeasonInfo.seasonName} has started!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startResponding(ctx,*,prompt):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period != 'preResponding':
        await ctx.send(f"Error! Current period is {period}!")
        return
    currentRound = seasonInfoDB['currentRound']
    with updateDBLock:
        RespondingPeriod.createResponseDB()
        if len(seasonInfoDB['prompts'])<currentRound:
            seasonInfoDB['prompts'].append(prompt)
        else:
            seasonInfoDB['prompts'][currentRound-1]=prompt
        seasonInfoDB['period'] = 'responding'
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    channel = bot.get_channel(channelIDs['prompts'])
    await channel.send(f"Round {str(currentRound)} has started! Your prompt is: \n"+
                       f"```{prompt}```\n"+
                       "Deadline is sometime. I'll implement a deadline feature later.")
    await ctx.send(f"Success! Responding period has started!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def closeResponding(ctx):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period != 'responding':
        await ctx.send(f"Error! Current period is {period}!")
        return
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        seasonInfoDB['period'] = 'preVoting'
        # get the number of responses sent 
        responseDB = RespondingPeriod.getResponseDB()
        messagesAsKeys = RespondingPeriod.userKeysToMessageKeys(responseDB)
        responseCount = len(messagesAsKeys)
        seasonInfoDB['numResponses'] = responseCount
        # eliminate people if they didn't send a response
        DNPs = []
        for aliveContestant in seasonInfoDB['aliveContestants']:
            if aliveContestant not in responseDB:
                DNPs.append(aliveContestant)
        if len(DNPs)!=0:
            for DNP in DNPs:
                del seasonInfoDB['aliveContestants'][DNP]
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    currentRound = seasonInfoDB['currentRound']
    channel = channel = bot.get_channel(channelIDs['prompts'])
    await channel.send(f"Round {str(currentRound)} responding is now closed!")
    await channel.send(f"We received {str(responseCount)} responses from "
                       +f"{str(len(responseDB))} contestants.")
    if len(DNPs)==0:
        await channel.send("All contestants sent responses. Hooray!")
    else:
        DNPDisplayNames = []
        for i,userID in enumerate(DNPs):
            user = await bot.fetch_user(int(userID))
            DNPDisplayNames.append(user.display_name)
        await channel.send(sopL(f"{lts(DNPDisplayNames)} ") 
                           +"failed to send responses and will be eliminated. So sad.")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startVoting(ctx):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period != 'preVoting':
        await ctx.send(f"Error! Current period is {period}!")
        return
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        seasonInfoDB['period'] = 'voting'
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    tempDict = RespondingPeriod.getResponseDB()
    responseDict = RespondingPeriod.userKeysToMessageKeys(tempDict)
    uniTable,allScreens,keywordsPerSection,sheet_id = GenerateVoting.generate_voting(responseDict)
    VotingPeriod.createVotingDBs(allScreens,keywordsPerSection)
    currentRound = seasonInfoDB['currentRound']
    channel = bot.get_channel(channelIDs['voting'])
    await channel.send(f"Round {str(currentRound)} voting has started!\n"
                       +f"https://docs.google.com/spreadsheets/d/{sheet_id}")
    
@bot.command()
@commands.is_owner()
@commands.dm_only()
async def closeVoting(ctx):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period != 'voting':
        await ctx.send(f"Error! Current period is {period}!")
        return
    with updateDBLock:
        seasonInfoDB = SeasonInfo.getSeasonInfoDB()
        seasonInfoDB['period'] = 'results'
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    currentRound = seasonInfoDB['currentRound']
    channel = channel = bot.get_channel(channelIDs['voting'])
    await channel.send(f"Round {str(currentRound)} voting is closed!")
    VPR = round(VotingPeriod.getVPR(),2)
    await channel.send(f"We got an average of {str(VPR)} votes per response.")

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
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period !='results':
        await ctx.send(f"Error! Current period is {period}!")
        return
    _, contestantScorePairs, sheetID = CalculateResults.generateResults()
    prizerNames, elimNames = CalculateResults.awardElimsAndPrizes(contestantScorePairs)
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
            seasonInfoDB['aliveContestants'][userID] = user.display_name
        SeasonInfo.updateSeasonInfoDB(seasonInfoDB)

@bot.command()
@commands.dm_only()
async def respond(ctx,*,response):
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if seasonInfoDB['period']!='responding':
        await ctx.send('Error! Responding is not currently open!')
        return
    currentRound = seasonInfoDB['currentRound']
    aliveContestants = seasonInfoDB['aliveContestants']
    userID = str(ctx.message.author.id)
    messageID = str(ctx.message.id)
    # check if the user is alive
    # if not, add them to the pool if it's r1, but reject their response if it's after r1
    if userID not in aliveContestants:
        if currentRound != 1:
            await ctx.send('Error! You are not currently a contestant!')
            return
        else:
            with updateDBLock:
                user = await bot.fetch_user(int(userID))
                seasonInfoDB['aliveContestants'][userID] = user.display_name
                SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    botMessage = RespondingPeriod.addResponse(userID,response,messageID)
    await ctx.send(botMessage)
    print(ctx.message.id)
    if botMessage[0]=='S':
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

@respond.error
@edit.error
async def responseError(ctx,error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Error! You didn't include a response!")
    else:
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
        await ctx.send(f"Something is wrong. Please report this error to SergeantSnivy.")

@deletevote.error
@clearvotes.error
async def voteDeleteError(ctx,error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Error! You didn't include a screen name to delete your vote from!")
    else:
        await ctx.send(f"Something is wrong. Please report this error to SergeantSnivy.")


bot.run(os.getenv('TOKEN')) # run the bot with the token


