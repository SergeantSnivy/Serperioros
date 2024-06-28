import json
import pandas as pd
import gspread
import math
import threading
import PrivateStuff as priv
from googleapiclient.discovery import build
from statistics import pstdev
from scipy.stats import skew
from VotingPeriod import getScreensDB, getVotesDB
from RespondingPeriod import getResponseDB, userKeysToMessageKeys
from SeasonInfo import getSeasonInfoDB
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

def getSortedLeaderboards():
    scoresDB = getScoresDB()
    leaderboard = sorted(scoresDB.items(), key=lambda x: (x[1]['finalScore'],-1*x[1]['skew']),reverse=True)
    print(leaderboard)
    formattedLB = []
    contestantScorePairs = []
    seasonInfoDB = getSeasonInfoDB()
    currentRound = seasonInfoDB['currentRound']
    prompt = seasonInfoDB['prompts'][currentRound-1]
    formattedLB.append(tuple([prompt]+[None]*7))
    headers = ('Rank','Contestant','Response','Score','St. Dev','Skew','Votes','VRD')
    formattedLB.append(headers)
    prevRank = 0
    pastPlacers = []
    for row in leaderboard:
        dataDict = row[1]
        userID = dataDict['author']
        contestant = getSeasonInfoDB()['aliveContestants'][userID]
        response = dataDict['content']
        score = dataDict['finalScore']
        stdev = dataDict['stdev']
        skew = dataDict['skew']
        votes = len(dataDict['voteScores'])
        VRD = str(sorted(dataDict['voteScores'],reverse=True))
        print(pastPlacers)
        if userID in pastPlacers:
            rank = '-'
            contestant = f'{contestant} [{str(pastPlacers.count(userID)+1)}]'
        else:
            rank = '#'+str(prevRank+1)
            prevRank+=1
            contestantScorePairs.append((userID,score))
        pastPlacers.append(userID)
        formattedLB.append((rank,contestant,response,score,stdev,skew,votes,VRD))
    return formattedLB,contestantScorePairs

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
    worksheet.update(leaderboard)
    return rV.id
  
def generateResults():
    createScoresDB()
    formattedLB, contestantScorePairs = getSortedLeaderboards()
    sheetID = create_google_sheet(formattedLB)
    print(sheetID)
    return formattedLB, contestantScorePairs, sheetID

def awardElimsAndPrizes(contestantScorePairs):
    seasonInfoDB = getSeasonInfoDB()
    if seasonInfoDB['elimFormat']=='vanilla':
        elims = eliminatedContestants(0.3,contestantScorePairs)
    elimDisplayNames = []
    for pair in elims:
        print(pair)
        userID = pair[0]
        print(userID)
        print(type(userID))
        elimDisplayNames.append(seasonInfoDB['aliveContestants'][userID])
        del seasonInfoDB['aliveContestants'][userID]
    prizers = prizingContestants(0.2,contestantScorePairs)
    prizerDisplayNames = []
    seasonInfoDB['currentPrizers'] = []
    for pair in prizers:
        print(pair)
        userID = pair[0]
        seasonInfoDB['currentPrizers'].append(userID)
        prizerDisplayNames.append(seasonInfoDB['aliveContestants'][userID])
    print(seasonInfoDB)
    SeasonInfo.updateSeasonInfoDB(seasonInfoDB)
    return prizerDisplayNames, elimDisplayNames
    


