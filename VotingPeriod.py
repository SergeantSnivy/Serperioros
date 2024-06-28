from ResponseClass import Response
from GenerateVoting import generate_voting
from Misc import singularOrPluralFromList as sopL
from Misc import listToString as lts
from SeasonInfo import getSeasonInfoDB, seasonInfoFileName
import json
import threading
import re

def getCurrentRound():
    return getSeasonInfoDB()['currentRound']

def getSeasonName():
    return getSeasonInfoDB()['seasonName']

def getScreensFileName():
    return f'{getSeasonName()}R{str(getCurrentRound())}Screens.json'

def getVotesFileName():
    return f'{getSeasonName()}R{str(getCurrentRound())}Votes.json'

def getKeywordsPerSectionFileName():
    return f'{getSeasonName()}R{str(getCurrentRound())}KeywordsPerSection.json'

accessDBLock = threading.Lock()

# screens DB is formatted like {keyword: {A: response, B: response, etc}}
# keywords per section DB is formatted like {sectionName: [keywordA, keywordB, etc]}
# votes DB is formatted like {userID: {'section': sectionName, 'screens': {keywordA: vote, keywordB: vote, etc}}
def createVotingDBs(allScreens,keywordsPerSection):
    with open(getScreensFileName(),'w') as f:
        json.dump(allScreens,f,indent=4)
    with open(getKeywordsPerSectionFileName(),'w') as f:
        json.dump(keywordsPerSection,f,indent=4)
    with open(getVotesFileName(),'w') as f:
        votesDB = {}
        json.dump(votesDB,f,indent=4)

def getScreensDB():
    with open(getScreensFileName(),'r') as f:
        screensDB = json.load(f)
    return screensDB

def getKeywordsPerSectionDB():
    with open(getKeywordsPerSectionFileName(),'r') as f:
        keywordsPerSectionDB = json.load(f)
    return keywordsPerSectionDB

def getVotesDB():
    with open(getVotesFileName(),'r') as f:
        votesDB = json.load(f)
    return votesDB

def updateVotesDB(newDB):
    with open(getVotesFileName(),'w') as f:
        json.dump(newDB,f,indent=4)

def checkVoteValidity(voteLetters,keysOnScreen):
    message = ''
    # check if vote has repeated letters
    if len(voteLetters)>len(set(voteLetters)):
        repeatedLetters = []
        for c in voteLetters:
            if voteLetters.count(c)>1 and c not in repeatedLetters:
                repeatedLetters.append(c)
        message += sopL(f'Error: {lts(repeatedLetters)} {{is/are}} repeated '
                        +'in your vote!')
    # check if vote is missing letters that are on the screen
    missingLetters = []
    for c in keysOnScreen:
        if c not in voteLetters:
            missingLetters.append(c)
    if len(missingLetters)>0:
        if not message:
            message = "Error: "
        else:
            message += " Additionally, "
        message += sopL(f'{lts(missingLetters)} {{is/are}} missing from '
                        +'your vote!')
    # check if vote has letters that aren't on the screen
    invalidLetters = []
    for c in voteLetters:
        if c not in keysOnScreen:
            invalidLetters.append(c)
    if len(invalidLetters)>0:
        if not message:
            message = "Error: "
        else:
            message += " Additionally, "
        message += sopL(f"{lts(invalidLetters)} {{is/are}} not {{a /}}"
                        +f"character{{/s}} on the screen you're voting on!")
    return message

#TODO: make screen names not case sensitive
def addVote(userID,keyword,letters):
    # make sure keyword exists
    allScreens = getScreensDB()
    if keyword not in allScreens:
        return f'Error: `{keyword}` is not a valid keyword!'
    with accessDBLock:
        votesDB = getVotesDB()
        # check if user has voted previously; if so, make some additional checks
        if userID in votesDB:
            # check if user has started voting on a different section
            keywordsPerSectionDB = getKeywordsPerSectionDB()
            userCurrentSection = votesDB[userID]['section']
            if keyword not in keywordsPerSectionDB[userCurrentSection]:
                return (f'Error: You have already started voting on section `{userCurrentSection}`!\n'
                        +f'Screen `{keyword}` is in a different section.')
            # check if user has already voted on this screen
            print(votesDB[userID]['screens'])
            if keyword in votesDB[userID]['screens']:
                return (f'Error: You have already sent a vote on screen {keyword}!\n'
                        +'To edit your vote, use `sp/editvote [keyword] [newvote]`.')
        keysOnScreen = [keyletter for keyletter in allScreens[keyword]]
        message = checkVoteValidity(letters,keysOnScreen)
        # if no errors have been raised, add vote to the DB
        if not message:
            # add user to vote DB if they're not there yet
            if userID not in votesDB:
                # find the section the user voted on
                keywordsPerSectionDB = getKeywordsPerSectionDB()
                for sectionName in keywordsPerSectionDB:
                    if keyword in keywordsPerSectionDB[sectionName]:
                        userNewSection = sectionName
                        break
                votesDB[userID] = {'section':userNewSection,'screens':{}}
            votesDB[userID]['screens'][keyword] = letters
            updateVotesDB(votesDB)
            message=f"Success! Your vote of `{keyword} {letters}` has been logged!"
    return message

def editVote(userID,keyword,letters):
    # make sure keyword exists
    allScreens = getScreensDB()
    if keyword not in allScreens:
        return f'Error: `{keyword}` is not a valid keyword!'
    with accessDBLock:
        votesDB = getVotesDB()
        # make sure user has already sent at least one vote 
        if userID not in votesDB:
            return 'Error! You have not sent any votes yet!'
        # make sure user has already voted on this particular screen
        if keyword not in votesDB[userID]['screens']:
            return f'Error! You have not voted on screen {keyword} yet!'
        keysOnScreen = [keyletter for keyletter in allScreens[keyword]]
        message = checkVoteValidity(letters,keysOnScreen)
        # if no errors have been raised, edit the vote in the DB
        if not message:
            votesDB[userID]['screens'][keyword] = letters
            updateVotesDB(votesDB)
            message=f"Success! Your vote on screen `{keyword}` is now `{letters}`!"
    return message

def deleteVote(userID,keyword):
    # make sure keyword exists
    allScreens = getScreensDB()
    if keyword not in allScreens:
        return f'Error: `{keyword}` is not a valid keyword!'
    with accessDBLock:
        votesDB = getVotesDB()
        # make sure user has already sent at least one vote 
        if userID not in votesDB:
            return 'Error! You have not sent any votes yet!'
        # make sure user has already voted on this particular screen
        if keyword not in votesDB[userID]['screens']:
            return f'Error! You have not voted on screen {keyword} yet!'
        del votesDB[userID]['screens'][keyword] 
        if len(votesDB[userID]['screens']) == 0:
            del votesDB[userID]
        updateVotesDB(votesDB)
        return f"Success! Your vote on screen `{keyword}` has been deleted!"
    
def clearVotes(userID):
    with accessDBLock:
        votesDB = getVotesDB()
        # make sure user has already sent at least one vote 
        if userID not in votesDB:
            return 'Error! You have not sent any votes yet!'
        del votesDB[userID]
        updateVotesDB(votesDB)
        return "Success! All your votes have been deleted!"
    
def getVPR():
    numResponses = getSeasonInfoDB()['numResponses']
    votesDB = getVotesDB()
    numScores = 0
    for userID in votesDB:
        screensDict = votesDB[userID]['screens']
        for screenName in screensDict:
            numScores += len(screensDict[screenName])
    return numScores/numResponses
        
    

