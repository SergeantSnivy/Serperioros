import json
import threading
from Misc import singularOrPluralFromNumber as sopN
from SeasonInfo import getSeasonInfoDB, seasonInfoFileName

updateDBLock = threading.Lock()

def getCurrentRound():
    return getSeasonInfoDB()['currentRound']

def getSeasonName():
    return getSeasonInfoDB()['seasonName']

def getAliveContestants():
    return getSeasonInfoDB()['aliveContestants']

def getResponsesPerPerson():
    return getSeasonInfoDB()['responsesPerPerson']

def getCurrentPrizers():
    return getSeasonInfoDB()['currentPrizers']

def getRespondingFileName():
    return f'{getSeasonName()}R{str(getCurrentRound())}Responses.json'

def createResponseDB():
    responseDB = {}
    with open(getRespondingFileName(),'w') as f:
        json.dump(responseDB,f,indent=4)

def getResponseDB():
    with open(getRespondingFileName(),'r') as f:
        responseDB = json.load(f)
    return responseDB

def getResponseDBWithMessageIDsAsKeys():
    userIDsAsKeys = getResponseDB()
    messageIDsAsKeys = {}
    for userID in userIDsAsKeys:
        for response in userIDsAsKeys[userID]:
            messageIDsAsKeys[response['ID']] = {'author':userID,'content':response['content']}
    return messageIDsAsKeys

def updateResponseDB(newDB):
    with open(getRespondingFileName(),'w') as f:
        json.dump(newDB,f,indent=4)

def maxResponses(contestant):
    if contestant in getCurrentPrizers():
        return getResponsesPerPerson()+1
    return getResponsesPerPerson()

def addResponse(contestant,response,messageID):
    with updateDBLock:
        if len(response)>1900:
            return f"Failed! Your response has {len(response)} characters, which is too long!"
        responseDB = getResponseDB()
        if contestant in responseDB:
            numRecorded = len(responseDB[contestant])
        else:
            numRecorded = 0
        if numRecorded<maxResponses(contestant):
            if contestant not in responseDB:
                responseDB[contestant] = []
            responseDB[contestant].append({'content':response,'ID':messageID})
            message = ('Success! The following response has been recorded:\n'
                    +f'`{response}`')
            updateResponseDB(responseDB)
        else:
            message = (sopN(f'Failed! You have already sent [{str(numRecorded)}] response{{/s}}, ')
                            +'which is the maximum allowed for this round!\nTo edit a response, '
                            +'type `sp/edit ')
            if maxResponses(contestant)>1:
                message += '[response #] '
            message += '[new response]`.'
    return message

def editResponse(contestant,responseNum,newResponse,messageID):
    if responseNum<1:
        return "Failed! You can't have less than 1 response, silly!"
    if responseNum>maxResponses(contestant):
        return sopN(f'Failed! You only get [{str(maxResponses(contestant))}] response{{/s}} this round, not {str(responseNum)}!')
    with updateDBLock:
        if len(newResponse)>1900:
            return f"Failed! Your response edit has {len(newResponse)} characters, which is too long!"
        responseDB = getResponseDB()
        if contestant in responseDB:
            numRecorded = len(responseDB[contestant])
        else:
            numRecorded = 0
        if responseNum>numRecorded:
            return sopN(f'Failed! You have only sent [{str(numRecorded)}] response{{/s}} so far, not {str(responseNum)}!')
        responseDB[contestant][responseNum-1] = {'content':newResponse,'ID':messageID}
        message = 'Success! Your '
        if maxResponses(contestant)!=1:
            message += f'#{str(responseNum)} '
        message += f'response now reads:\n`{newResponse}`'
        updateResponseDB(responseDB)
    return message



    
    

