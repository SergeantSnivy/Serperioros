import json
import pandas as pd
import gspread
from gspread.utils import ValueInputOption
import math
import threading
import PrivateStuff as priv
from googleapiclient.discovery import build
from statistics import pstdev
from scipy.stats import skew
from VotingPeriod import getScreensDB, getVotesDB
from RespondingPeriod import getResponseDB, userKeysToMessageKeys
from SeasonInfo import getSeasonInfoDB
from Misc import sheetsRowArray
import SeasonInfo

updateDBLock = threading.Lock()

def getCurrentRound():
    return getSeasonInfoDB()['currentRound']

def getSeasonName():
    return getSeasonInfoDB()['seasonName']

def getScoresFileName():
    return f'{getSeasonName()}R{str(getCurrentRound())}Scores.json'

def getElimsFileName():
    return f'{getSeasonName()}R{str(getCurrentRound())}Elims.json'

def nonBankerRound(num):
    if num - math.floor(num) < 0.5:
        return math.floor(num)
    return math.ceil(num)

def prizingContestants(threshold,leaderboard):
    numContestants = len(leaderboard)
    numPrizers = nonBankerRound(max(1,threshold*numContestants))
    return leaderboard[:numPrizers]

def eliminatedContestants(threshold,leaderboard):
    numContestants = len(leaderboard)
    print(numContestants)
    numEliminated = nonBankerRound(max(1,threshold*numContestants))
    print(numEliminated)
    return leaderboard[numContestants-numEliminated:numContestants]

def createScoresDB():
    scoresDB = userKeysToMessageKeys(getResponseDB())
    for responseID in scoresDB:
        scoresDB[responseID]['voteScores'] = []
    votesDB = getVotesDB()
    allScreens = getScreensDB()
    # add each 
    for userID in votesDB:
        print('user')
        for keyword in votesDB[userID]['screens']:
            voteLetters = votesDB[userID]['screens'][keyword]
            screenLen = len(allScreens[keyword])
            for letter in allScreens[keyword]:
                placeInVote = voteLetters.index(letter)
                scoreToAdd = (screenLen-placeInVote-1)/(screenLen-1)
                responseID = allScreens[keyword][letter]
                scoresDB[responseID]['voteScores'].append(scoreToAdd)
    # get final score, stdev, skew
    for responseID in scoresDB:
        voteScores = scoresDB[responseID]['voteScores']
        scoresDB[responseID]['finalScore'] = sum(voteScores)/len(voteScores)
        scoresDB[responseID]['stdev'] = pstdev(voteScores)
        # handle invalid skews
        if len(voteScores)<3 or all([voteScores[n]==voteScores[0] for n in range(1,len(voteScores))]):
            scoresDB[responseID]['skew'] = 0
        else:
            scoresDB[responseID]['skew'] = skew(voteScores)
    print('cool')
    with open(getScoresFileName(),'w') as f:
        json.dump(scoresDB,f,indent=4)

def createElimsDB(eliminatedContestants):
    with open(getElimsFileName(),'w') as f:
        json.dump({'elims':eliminatedContestants},f,indent=4)

def getScoresDB():
    with open(getScoresFileName(),'r') as f:
        scoresDB = json.load(f)
    return scoresDB

def getElimsDB():
    with open(getElimsFileName(),'r') as f:
        elimsDB = json.load(f)
    return elimsDB

# note to self: when the API encounters a merged cell,
# it looks at the subarray of values with positions of cells in the merge,
# takes the top left one, and skips over the rest.
# to adapt to this, put arbitrary values in positions that you want to be skipped over
def getSortedLeaderboards():
    scoresDB = getScoresDB()
    leaderboard = sorted(scoresDB.items(), key=lambda x: (x[1]['finalScore'],-1*x[1]['skew']),reverse=True)
    print(leaderboard)
    formattedLB = []
    contestantScorePairs = []
    statsRows = []
    seasonInfoDB = getSeasonInfoDB()
    currentRound = seasonInfoDB['currentRound']
    prompt = seasonInfoDB['prompts'][currentRound-1]
    formattedLB.append(tuple([prompt]+[None]*5))
    headers = ('Rank','Book','Contestant/\nResponse','Score','StDev/\nSkew','VRD')
    formattedLB.append(headers)
    prevRank = 0
    pastPlacers = []
    for row in leaderboard:
        dataDict = row[1]
        userID = dataDict['author']
        userData = getSeasonInfoDB()['aliveContestants'][userID]
        if 'bookLink' in userData:
            book = f'=image("{userData['bookLink']}")'
        else:
            book = '=image("https://files.catbox.moe/q6k2t9.png")'
        contestant = userData['displayName']
        response = dataDict['content']
        # sanitize potential formulas
        if response[0] in ['=','+']:
            response = "'" + response
        score = dataDict['finalScore']
        stdev = dataDict['stdev']
        skew = dataDict['skew']
        votes = len(dataDict['voteScores'])
        VRD = ('''=lambda(votes,SPARKLINE(transpose(sort(transpose(ARRAYFORMULA(FILTER(votes, votes <> "")'''
               +'''-AVERAGE(votes))),1,FALSE)),{"charttype","column";"ymin",-AVERAGE(votes);"ymax",1-AVERAGE(votes)}))'''
               +f'({sheetsRowArray(sorted(dataDict['voteScores'],reverse=True))})')
        print(pastPlacers)
        statsRows.append((contestant,response,score,stdev,skew))
        if userID in pastPlacers:
            rank = '-'
            contestant = f'{contestant} [{str(pastPlacers.count(userID)+1)}]'
        else:
            rank = '#'+str(prevRank+1)
            prevRank+=1
            contestantScorePairs.append((userID,score))
        pastPlacers.append(userID)
        row1 = (rank,book,contestant,score,stdev,VRD)
        row2 = (None,None,response,score,skew,None)
        formattedLB.append(row1)
        formattedLB.append(row2)
    return formattedLB,contestantScorePairs,statsRows

def fill_excel_sheet(file_path,leaderboard):
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        currentDF = pd.DataFrame(leaderboard)
        currentDF = currentDF.fillna('')
        currentDF.to_excel(writer,sheet_name=f'Results',index=False,
                            header=None)

# imports data from Excel sheet into a Google Sheet
# the Google Sheet will be formatted based on a results template
def create_google_sheet(leaderboard):
    client = gspread.authorize(priv.creds)
    rV = client.copy(priv.results_template_id,title="Testing")
    for email in priv.my_emails:
        rV.share(email,perm_type='user',role='writer')
    rV.share('',perm_type='anyone',role='reader')
    try:
        worksheet = rV.get_worksheet(0)
        worksheet.resize(rows=len(leaderboard), cols=len(leaderboard[0]))
    except:
        worksheet = rV.add_worksheet(title=f"Results", rows=len(leaderboard), cols=len(leaderboard[0]))
    worksheet.update(leaderboard,value_input_option=ValueInputOption.user_entered)
    return rV.id
  
def generateResults(getSheet=True):
    createScoresDB()
    formattedLB, contestantScorePairs, statsRows = getSortedLeaderboards()
    if getSheet:
        sheetID = create_google_sheet(formattedLB)
        print(sheetID)
    else:
        sheetID = None
    return formattedLB, contestantScorePairs, statsRows, sheetID

def awardElimsAndPrizes(contestantScorePairs):
    seasonInfoDB = getSeasonInfoDB()
    if seasonInfoDB['elimFormat']=='vanilla':
        elims = eliminatedContestants(0.3,contestantScorePairs)
    elimIDs = []
    for pair in elims:
        print(pair)
        userID = pair[0]
        print(userID)
        print(type(userID))
        elimIDs.append(userID)
        seasonInfoDB['eliminatedContestants'][userID] = seasonInfoDB['aliveContestants'][userID]
        del seasonInfoDB['aliveContestants'][userID]
    prizers = prizingContestants(0.2,contestantScorePairs)
    prizerIDs = []
    seasonInfoDB['currentPrizers'] = []
    for pair in prizers:
        print(pair)
        userID = pair[0]
        seasonInfoDB['currentPrizers'].append(userID)
        prizerIDs.append(userID)
    print(seasonInfoDB)
    print("Prizer IDs:")
    print(prizerIDs)
    SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    return prizerIDs, elimIDs
    


