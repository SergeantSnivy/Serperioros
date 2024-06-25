import discord
import random
from discord.ext import commands
import os
import RespondingPeriod
import GenerateVoting
import VotingPeriod
import SeasonInfo
from dotenv import load_dotenv


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
    currentRound = SeasonInfo.getSeasonInfoDB()['currentRound']
    channel = bot.get_channel(channelIDs['prompts'])
    await channel.send(f"Round {str(currentRound)} has started! Your prompt is: \n"+
                       f"```{prompt}```\n"+
                       "Deadline is sometime. I'll implement a deadline feature later.")
    RespondingPeriod.createResponseDB()
    seasonInfoDB = SeasonInfo.getSeasonInfoDB()
    if len(seasonInfoDB['prompts'])<currentRound:
        seasonInfoDB['prompts'].append(prompt)
    else:
        seasonInfoDB['prompts'][currentRound-1]=prompt
    SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    await ctx.send(f"Success! Responding period has started!")

@bot.command()
@commands.is_owner()
@commands.dm_only()
async def startVoting(ctx):
    tempDict = RespondingPeriod.getResponseDB()
    responseDict = RespondingPeriod.userKeysToMessageKeys(tempDict)
    uniTable,allScreens,keywordsPerSection,sheet_id = GenerateVoting.generate_voting(responseDict)
    VotingPeriod.createVotingDBs(allScreens,keywordsPerSection)
    currentRound = SeasonInfo.getSeasonInfoDB()['currentRound']
    channel = bot.get_channel(channelIDs['voting'])
    await channel.send(f"Round {str(currentRound)} voting has started!\n"
                       +f"https://docs.google.com/spreadsheets/d/{sheet_id}")

@bot.command()
@commands.dm_only()
async def respond(ctx,*,response):
    currentRound = SeasonInfo.getSeasonInfoDB()['currentRound']
    aliveContestants = SeasonInfo.getSeasonInfoDB()['aliveContestants']
    userID = str(ctx.message.author.id)
    messageID = str(ctx.message.id)
    # check if the user is alive
    # if not, add them to the pool if it's r1, but reject their response if it's after r1
    if userID not in aliveContestants:
        if currentRound != 1:
            await ctx.send('Failure! You are not currently a contestant!')
            return
        else:
            seasonInfoDB = SeasonInfo.getSeasonInfoDB()
            seasonInfoDB['aliveContestants'].append(userID)
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
    aliveContestants = SeasonInfo.getSeasonInfoDB()['aliveContestants']
    userID = str(ctx.message.author.id)
    messageID = str(ctx.message.id)
    # check if the user is alive
    # if not, reject their edit
    if userID not in aliveContestants:
        await ctx.send('Failure! You are not an alive contestant!')
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
async def vote(ctx,keyword,letters):
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
    userID = str(ctx.message.author.id)
    botMessage = VotingPeriod.clearVotes(userID)
    await ctx.send(botMessage)
    if botMessage[0]=='S':
        channel = bot.get_channel(channelIDs['log'])
        user = await bot.fetch_user(int(userID))
        username = user.name
        await channel.send(f'{username} has cleared all their votes')




bot.run(os.getenv('TOKEN')) # run the bot with the token


