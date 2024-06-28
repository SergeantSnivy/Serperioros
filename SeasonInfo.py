import json

seasonName = 'SnimeraAlphaTest2'
seasonInfoFileName = f'{seasonName}Info.json'

def createSeasonInfoDB():
    seasonInfoDB = {'currentRound':1,'seasonName':seasonName,'responsesPerPerson':3,
                    'period':'preResponding','aliveContestants':{},'currentPrizers':[],
                    'prompts':[],'numResponses':0,'elimFormat':'vanilla'}
    with open(seasonInfoFileName,'w') as f:
        json.dump(seasonInfoDB,f,indent=4)

def getSeasonInfoDB():
    with open(seasonInfoFileName,'r') as f:
        seasonInfoDB = json.load(f)
    return seasonInfoDB

def updateSeasonInfoDB(newDB):
    with open(seasonInfoFileName,'w') as f:
        json.dump(newDB,f,indent=4)