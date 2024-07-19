import json

seasonName = 'SnimeraFullAlphaTest2'
seasonInfoFileName = f'{seasonName}Info.json'

def createSeasonInfoDB():
    seasonInfoDB = {'currentRound':1,'seasonName':seasonName,'responsesPerPerson':1,
                    'period':'preResponding','aliveContestants':{},'currentPrizers':[],
                    'prompts':[],'numResponses':0,'elimFormat':'vanilla','deadline':None,
                    'deadlineMode':'min','deadlineLen':5,'enforceDeadline':True,
                    'limitType':'word','limit':10}
    with open(seasonInfoFileName,'w') as f:
        json.dump(seasonInfoDB,f,indent=4)

def getSeasonInfoDB():
    with open(seasonInfoFileName,'r') as f:
        seasonInfoDB = json.load(f)
    return seasonInfoDB

def updateSeasonInfoDB(newDB):
    with open(seasonInfoFileName,'w') as f:
        json.dump(newDB,f,indent=4)

def getDisplayNamesFromIDs(IDList):
    return [getSeasonInfoDB()['aliveContestants'][ID]['displayName'] for ID in IDList]