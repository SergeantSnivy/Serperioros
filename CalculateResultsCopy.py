import json
import pandas as pd
import gspread
from gspread.utils import ValueInputOption, rowcol_to_a1
from gspread_formatting import *
import math
import threading
import PrivateStuff as priv
from googleapiclient.discovery import build
from statistics import pstdev
from scipy.stats import skew
from VotingPeriod import getScreensDB, getVotesDB
from RespondingPeriod import getResponseDB, userKeysToMessageKeys
from SeasonInfo import getSeasonInfoDB, getSeasonName, updateSeasonInfoDB
from Stats import getSRPairsFromContestantScorePairs
from Misc import sheetsRowArray

topColor = (0.29411764705882354,0.7568627450980392,0.3764705882352941)
midColor = (0.9647058823529412,1,0.3607843137254902)
bottomColor = (0.8117647058823529,0.27058823529411763,0.27058823529411763)

def getCellColorFromScore(minScore,maxScore,currentScore):
    relativeScore = (currentScore-minScore)/(maxScore-minScore)
    print(relativeScore)
    if relativeScore>0.5:
        maxColor = topColor
        minColor = midColor
        colorScore = relativeScore*2-1
    else:
        maxColor = midColor
        minColor = bottomColor
        colorScore = relativeScore*2
    rgbList = []
    for i in range(3):
        rgbList.append((maxColor[i]-minColor[i])*colorScore+minColor[i])
    return ColorStyle(rgbColor=Color(rgbList[0],rgbList[1],rgbList[2]))

updateDBLock = threading.Lock()

def getCurrentRound():
    return 5

def getScoresFileName():
    return f'testScoresDB.json'

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
    scoresDB = {}
    for responseID in range(101):
        scoresDB[responseID] = {}
        scoresDB[responseID]['voteScores'] = [1,2]
        voteScores = scoresDB[responseID]['voteScores']
        scoresDB[responseID]['author']=f'person{str(responseID)}'
        scoresDB[responseID]['content']='Response'
        scoresDB[responseID]['finalScore'] = (responseID-1)/100
        scoresDB[responseID]['stdev'] = 0.2
        scoresDB[responseID]['skew'] = 2
    print('cool')
    with open('testScoresDB.json','w') as f:
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
    currentRound = getCurrentRound()
    numPrizers = 2
    prompt = "The prompt"
    formattedLB.append(tuple([prompt]+[None]*5))
    headers = ('Rank','Book','Contestant/\nResponse','Score','StDev/\nSkew','VRD')
    formattedLB.append(headers)
    prevRank = 0
    pastPlacers = []
    colorArray = []
    for i in range(2):
        colorArray.append([None]*6)
    minPercent = leaderboard[-1][1]['finalScore']
    maxPercent = leaderboard[0][1]['finalScore']
    for row in leaderboard:
        dataDict = row[1]
        userID = dataDict['author']
        userData = []
        if 'bookLink' in userData:
            book = f'=image("{userData['bookLink']}")'
        else:
            book = '=image("https://files.catbox.moe/q6k2t9.png")'
        contestant = userID
        response = dataDict['content']
        # sanitize potential formulas
        if response[0] in ['=','+',"'"]:
            response = "'" + response
        score = dataDict['finalScore']
        stdev = dataDict['stdev']
        skew = dataDict['skew']
        votes = len(dataDict['voteScores'])
        VRD = ('''=lambda(votes,SPARKLINE(transpose(sort(transpose(ARRAYFORMULA(FILTER(votes, votes <> "")'''
               +'''-AVERAGE(votes))),1,FALSE)),{"charttype","column";"ymin",-AVERAGE(votes);"ymax",1-AVERAGE(votes)}))'''
               +f'({sheetsRowArray(sorted(dataDict['voteScores'],reverse=True))})')
        statsRows.append((contestant,response,score,stdev,skew))
        if userID in pastPlacers:
            rank = '-'
            contestant = f'{contestant} [{str(pastPlacers.count(userID)+1)}]'
        else:
            rank = str(prevRank+1)
            prevRank+=1
            contestantScorePairs.append((userID,score))
        pastPlacers.append(userID)
        row1 = (rank,book,contestant,score,stdev,VRD)
        row2 = (None,None,response,score,skew,None)
        formattedLB.append(row1)
        formattedLB.append(row2)
        currentColor = getCellColorFromScore(minPercent,maxPercent,score)
        print(currentColor)
        cellWithColor = CellFormat(backgroundColorStyle=currentColor)
        for i in range(2):
            colorArray.append([cellWithColor]*6)
    print(len(formattedLB))
    print(len(colorArray))
    # add DNPs to contestantScorePairs and statsRows if not vanilla (necessary for them to be in SRs)
    # formattedLB / statsRows uses display name, contestantScorePairs uses user ID
    return formattedLB,colorArray,contestantScorePairs,statsRows

def getPhaseLeaderboard(currentRoundPairs):
    currentRoundSRPairs = currentRoundPairs
    print(currentRoundSRPairs)
    totalSRPairs = []
    formattedLB = []
    currentRound = getCurrentRound()
    headers = ("Rank","Book","Contestant","Total",f"Round {str(currentRound-1)}",f"Round {str(currentRound)}")
    formattedLB.append(headers)
    for userID,currentSR in currentRoundSRPairs:
        book = '=image("https://files.catbox.moe/q6k2t9.png")'
        prevSR = 0
        displayName = "Person"
        totalSR = prevSR+currentSR
        formattedLB.append([None,book,displayName,totalSR,prevSR,currentSR])
        totalSRPairs.append((userID,totalSR))
    totalSRPairs.sort(key=lambda x: x[1],reverse=True)
    totalSRIndex = headers.index("Total")
    print('\n')
    print(totalSRIndex)
    print(formattedLB)
    formattedLB = [formattedLB[0]] + sorted(formattedLB[1:],key=lambda x: x[totalSRIndex],reverse=True)
    # add ranks after sort
    for i,row in enumerate(formattedLB[1:]):
        formattedLB[i+1][0]=f"#{str(i+1)}"
    return formattedLB,totalSRPairs,currentRoundSRPairs

# imports data from 2d array into a Google Sheet
# the Google Sheet will be formatted based on a results template
def create_google_sheet(leaderboard,templateID):
    values = leaderboard[0]
    colors = leaderboard[1]
    client = gspread.authorize(priv.creds)
    rV = client.copy(templateID,title="Testing")
    for email in priv.my_emails:
        rV.share(email,perm_type='user',role='writer')
    rV.share('',perm_type='anyone',role='reader')
    try:
        worksheet = rV.get_worksheet(0)
        worksheet.resize(rows=len(values), cols=len(values[0]))
    except:
        worksheet = rV.add_worksheet(title=f"Results", rows=len(values), cols=len(values[0]))
    worksheet.update(values,value_input_option=ValueInputOption.user_entered)
    nameColorPairs = []
    if len(colors)!=0:
        for row in range(len(colors)):
            for col in range(len(colors[0])):
                if colors[row][col]:
                    nameColorPairs.append((rowcol_to_a1(row+1,col+1),colors[row][col]))
        format_cell_ranges(worksheet,nameColorPairs)
    return rV.id
  
def generateResults(getSheet=True):
    createScoresDB()
    formattedLB, colorArray, contestantScorePairs, statsRows = getSortedLeaderboards()
    if getSheet:
        sheetID = create_google_sheet((formattedLB,colorArray),priv.results_template_id)
        print(sheetID)
    else:
        sheetID = None
    return formattedLB, contestantScorePairs, statsRows, sheetID

def generatePhaseResults(contestantScorePairs,getSheet=True):
    formattedLB, totalSRPairs, currentRoundSRPairs = getPhaseLeaderboard(contestantScorePairs)
    if getSheet:
        sheetID = create_google_sheet((formattedLB,[]),priv.phase_results_template_id)
        print(sheetID)
    else:
        sheetID = None
    return formattedLB, totalSRPairs, currentRoundSRPairs, sheetID

def awardElimsAndPrizes(contestantScorePairs):
    seasonInfoDB = getSeasonInfoDB()
    prizers = prizingContestants(0.2,contestantScorePairs)
    prizerIDs = []
    seasonInfoDB['currentPrizers'] = []
    for pair in prizers:
        print(pair)
        userID = pair[0]
        seasonInfoDB['currentPrizers'].append(userID)
        prizerIDs.append(userID)
    nonElim = False
    # if rolling average, write current scores to prevScore in seasonInfoDB, then get rolling average for elims
    if seasonInfoDB['elimFormat'] == 'rollingAverage':
        _, potentialNewPairs, currentRoundSRPairs, _ = generatePhaseResults(contestantScorePairs,getSheet=False)
        for userID, currentScore in currentRoundSRPairs:
            seasonInfoDB['aliveContestants'][userID]['prevScore'] = currentScore
        if seasonInfoDB['currentRound']!=1:
            oldPairs = contestantScorePairs
            contestantScorePairs = potentialNewPairs
        else:
            nonElim = True
    # eliminate people if there's eliminations
    elimIDs = []
    if not nonElim:
        elims = eliminatedContestants(0.3,contestantScorePairs)
        for pair in elims:
            print(pair)
            userID = pair[0]
            print(userID)
            print(type(userID))
            elimIDs.append(userID)
            seasonInfoDB['eliminatedContestants'][userID] = seasonInfoDB['aliveContestants'][userID]
            del seasonInfoDB['aliveContestants'][userID]
    print(seasonInfoDB)
    print("Prizer IDs:")
    print(prizerIDs)
    # recalculate previous SRs without eliminated contestants if that is enabled
    if seasonInfoDB['elimFormat'] == 'rollingAverage' and seasonInfoDB['currentRound'] != 1 and seasonInfoDB['recalcPrev']:
        onlyAlivePairs = []
        print(oldPairs)
        for pair in oldPairs:
            if pair[0] in seasonInfoDB['aliveContestants']:
                onlyAlivePairs.append(pair)
        print(onlyAlivePairs)
        recalcedSRs = getSRPairsFromContestantScorePairs(onlyAlivePairs)
        for userID,newSR in recalcedSRs:
            seasonInfoDB['aliveContestants'][userID]['prevScore'] = newSR
    updateSeasonInfoDB(seasonInfoDB)
    return prizerIDs, elimIDs
    


_,pairs,_,_,=generateResults()
a=generatePhaseResults(pairs)
