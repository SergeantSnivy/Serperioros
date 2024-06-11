import json

seasonName = 'SnimeraTestS1'
seasonInfoFileName = f'{seasonName}Info.json'

def createSeasonInfoDB():
    seasonInfoDB = {'currentRound':1,'seasonName':seasonName,'responsesPerPerson':1,
                    'aliveContestants':[],'currentPrizers':[],'prompts':[]}
    with open(seasonInfoFileName,'w') as f:
        json.dump(seasonInfoDB,f,indent=4)

def getSeasonInfoDB():
    with open(seasonInfoFileName,'r') as f:
        seasonInfoDB = json.load(f)
    return seasonInfoDB

def updateSeasonInfoDB(newDB):
    with open(seasonInfoFileName,'w') as f:
        json.dump(newDB,f,indent=4)