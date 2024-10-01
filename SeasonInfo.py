import json
import os
from PrivateStuff import pathToBot

'''seasonParamsMutable =  {'currentRound':{'default':1,'convert': lambda x: int(x), 'permitted': 
                                       lambda x: x.isnumeric() and int(x)>0},
                        'seasonName':{'default':seasonName,'convert': lambda x: x, 'permitted': 
                                     lambda x: len(x)<100},
                        'responsesPerPerson':{'default':1,'convert': lambda x: int(x), 'permitted': 
                                             lambda x: x.isnumeric() and int(x)>0},
                        'period':{'default':'preResponding','convert': lambda x: x, 'permitted': 
                                  lambda x: x in ['preResponding','responding','preVoting','voting','results','over']},
                        'elimFormat':{'default':'rollingAverage','convert': lambda x: x, 'permitted': 
                                      lambda x: x in ['vanilla', 'rollingAverage']},
                        'deadline':{'default':None,'convert': lambda x: int(x), 'permitted':
                                    lambda x: }
                       }
seasonParamsImmutable = {'aliveContestants':{},
                         'eliminatedContestants':{},
                         'currentPrizers':[],
                         'prompts':[],
                         'numResponses':0}'''
def validJSON(JSON):
    try:
        json.load(JSON)
        return True
    except:
        return False
    
def createSeasonInfoDB(seasonName):
    seasonInfoDB = {'currentRound':1,'seasonName':seasonName,'responsesPerPerson':1,
                    'period':'preResponding','aliveContestants':{},
                    'eliminatedContestants':{},'currentPrizers':[],'currentDNPs':[],
                    'prompts':[],'numResponses':0,'elimFormat':'rollingAverage','recalcPrev':False,
                    'deadline':None,'deadlineMode':'min','deadlineLen':7,'enforceDeadline':True,
                    'limitType':'word','limit':10}
    # add season name to meta text file
    os.chdir(pathToBot)
    try:
        os.mkdir("metaInfo")
    except:
        pass
    os.chdir("metaInfo")
    with open('currentSeasonName.txt','w') as f:
        f.write(seasonName)
    # create season info folder and DB from seasonName
    os.chdir(pathToBot)
    try:
        os.mkdir(seasonName)
    except:
        pass
    os.chdir(seasonName)
    with open(getSeasonInfoFileName(),'w') as f:
        json.dump(seasonInfoDB,f,indent=4)

def getSeasonName():
    # season name should always be the name of the current directory
    return os.getcwd().split('\\')[-1]

def getSeasonInfoFileName():
    return f'{getSeasonName()}Info.json'

def getSeasonInfoBackupFileName():
    return f'{getSeasonName()}InfoBackup.json'

def getSeasonInfoDB():
    with open(getSeasonInfoFileName(),'r') as f:
        seasonInfoDB = json.load(f)
    return seasonInfoDB

def updateSeasonInfoDB(newDB):
    with open(getSeasonInfoFileName(),'w') as f:
        json.dump(newDB,f,indent=4)

def getSeasonInfoBackupDB():
    with open(getSeasonInfoBackupFileName(),'r') as f:
        seasonInfoBackupDB = json.load(f)
    return seasonInfoBackupDB

def updateSeasonInfoBackupDB(newDB):
    with open(getSeasonInfoBackupFileName(),'w') as f:
        json.dump(newDB,f,indent=4)

def getDisplayNamesFromIDs(IDList,alive):
    if alive:
        contestantType = 'aliveContestants'
    else:
        contestantType = 'eliminatedContestants'
    return [getSeasonInfoDB()[contestantType][ID]['displayName'] for ID in IDList]