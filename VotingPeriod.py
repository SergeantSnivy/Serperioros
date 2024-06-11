from ResponseClass import Response
from GenerateVoting import generate_voting
from Misc import singularOrPluralFromList as sopL
from Misc import listToString as lts
import json
import re

currentRound = 7
seasonName = 'Snimera'
aliveContestants = ['sergeantsnivy','cloverpepsi']
maxResponses = 2
screensFileName = f'{seasonName}R{str(currentRound)}Screens.json'
votesFileName = f'{seasonName}R{str(currentRound)}Votes.json'

# screens DB is formatted like {keyword: {A: response, B: response, etc}}
# votes DB is formatted like {keyword: [vote, vote, etc]}
def createVotingDBs(allScreens):
    with open(screensFileName,'w') as f:
        json.dump(allScreens,f)
    with open(votesFileName,'w') as f:
        votesDB = {}
        for keyword in allScreens:
            votesDB[keyword]=[]
        json.dump(votesDB,f)

def getScreensDB():
    with open(screensFileName,'r') as f:
        screensDB = json.load(f)
    return screensDB

def getVotesDB():
    with open(votesFileName,'r') as f:
        votesDB = json.load(f)
    return votesDB

def updateVotesDB(newDB):
    with open(votesFileName,'w') as f:
        json.dump(newDB,f)

def addVote(keyword,letters):
    message = ''
    # check if keyword exists
    allScreens = getScreensDB()
    if keyword not in allScreens:
        return f'Error: `{keyword}` is not a valid keyword!'
    # TODO: check if user has already voted on this screen

    # TODO: check if user has started voting on a different section (might require changing DB format)

    # check if vote has repeated letters
    if len(letters)!=len(set(letters)):
        repeatedLetters = []
        for c in letters:
            if letters.count(c)>1 and c not in repeatedLetters:
                repeatedLetters.append(c)
        message += sopL(f'Error: {lts(repeatedLetters)} {{is/are}} repeated '
                        +'in your vote!')
    # check if vote is missing letters that are on the screen
    uniSubTable = [keyletter for keyletter in allScreens[keyword]]
    if len(letters)!=len(allScreens[keyword]):
        missingLetters = []
        for c in uniSubTable:
            if c not in letters:
                missingLetters.append(c)
        if not message:
            message = "Error: "
        else:
            message += " Additionally, "
        message += sopL(f'{lts(missingLetters)} {{is/are}} missing from '
                        +'your vote!')
    # check if vote has letters that aren't on the screen
    invalidLetters = []
    for c in letters:
        if c not in uniSubTable:
            invalidLetters.append(c)
    if invalidLetters:
        if not message:
            message = "Error: "
        else:
            message += " Additionally, "
        message += sopL(f"{lts(invalidLetters)} {{is/are}} not {{a /}}"
                        +f"character{{/s}} on the screen you're voting on!")
    # now we can add the vote to the DB since we know it's valid
    if not message:
        message="Success! Your vote of `{keyword} {letters}` has been logged!"
        votesDB = getVotesDB
        votesDB[keyword].append(letters)
        updateVotesDB(votesDB)
    return message
    
# TODO: move this to a results calculation file
def addScoresFromVote(keyword,letters):
    allScreens = getScreensDB()
    uniSubTable = [keyletter for keyletter in allScreens[keyword]]
    screenLen=len(letters)
    for placeInScreen,c in enumerate(uniSubTable):
        placeInVote=letters.index(c)
        scoreToAdd=(screenLen-placeInVote-1)/(screenLen-1)
        allScreens[keyword][placeInScreen].addVoteScore(scoreToAdd)
