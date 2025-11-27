import json
import threading
from Misc import singularOrPluralFromNumber as sopN, singularOrPluralFromList as sopL, listToString as lts, addDays, addMinutes
from SeasonInfo import getSeasonInfoDB, updateSeasonInfoDB, getSeasonName
from TechnicalTools import reformat, getWords
from datetime import datetime

updateDBLock = threading.Lock()

def getCurrentRound():
    return getSeasonInfoDB()['currentRound']

def getAliveContestants():
    return getSeasonInfoDB()['aliveContestants']

def getResponsesPerPerson():
    return getSeasonInfoDB()['responsesPerPerson']

def getCurrentPrizers():
    return getSeasonInfoDB()['currentPrizers']

def getLimitType():
    return getSeasonInfoDB()['limitType']

def getLimit():
    return getSeasonInfoDB()['limit']

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

def userKeysToMessageKeys(dbWithUserKeys):
    dbWithMessageKeys = {}
    for userID in dbWithUserKeys:
        for response in dbWithUserKeys[userID]:
            dbWithMessageKeys[response['ID']] = {'author':userID,'content':response['content']}
    return dbWithMessageKeys

def messageKeysToUserKeys(dbWithMessageKeys):
    dbWithUserKeys = {}
    for messageID in dbWithMessageKeys:
        response = dbWithMessageKeys['messageID']
        userID = response['author']
        if userID not in dbWithUserKeys:
            dbWithUserKeys[userID] = [{'ID':messageID,'content':response['content']}]
        else:
            dbWithUserKeys[userID].append({'ID':messageID,'content':response['content']})
    return dbWithUserKeys

def updateResponseDB(newDB):
    with open(getRespondingFileName(),'w') as f:
        json.dump(newDB,f,indent=4)

def maxResponses(contestant):
    if contestant in getCurrentPrizers():
        return getResponsesPerPerson()+1
    return getResponsesPerPerson()

def addResponse(contestant,response:str,messageID):
    if len(response)>1900:
        return f"Failed! Your response has {len(response)} characters, which is too long!"
    response = reformat(response)
    if getLimitType() == 'word':
        numWords = len(getWords(response))
        wordLimit = getLimit()
        if numWords>wordLimit:
            return f"Failed! Your response has {str(numWords)} words, which exceeds the limit of {str(wordLimit)}!"
    elif getLimitType() == 'char':
        numChars = len(response)
        charLimit = getLimit()
        if numChars>charLimit:
            return f"Failed! Your response has {str(numChars)} characters, which exceeds the limit of {str(charLimit)}!"
    print("addResponse")
    with updateDBLock:
        responseDB = getResponseDB()
        if contestant in responseDB:
            numRecorded = len(responseDB[contestant])
        else:
            numRecorded = 0
        if numRecorded<maxResponses(contestant):
            if contestant not in responseDB:
                responseDB[contestant] = []
            responseDB[contestant].append({'content':response,'ID':messageID})
            updateResponseDB(responseDB)
            message = ('Success! The following response has been recorded:\n'
                    +f'`{response}`')
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
    if len(newResponse)>1900:
        return f"Failed! Your response edit has {len(newResponse)} characters, which is too long!"
    if getLimitType() == 'word':
        numWords = len(getWords(newResponse))
        wordLimit = getLimit()
        if numWords>wordLimit:
            return f"Failed! Your response edit has {str(numWords)} words, which exceeds the limit of {str(wordLimit)}!"
    elif getLimitType() == 'char':
        numChars = len(newResponse)
        charLimit = getLimit()
        if numChars>charLimit:
            return f"Failed! Your response edit has {str(numChars)} characters, which exceeds the limit of {str(charLimit)}!"
    print("editResponse")
    with updateDBLock:
        responseDB = getResponseDB()
        if contestant in responseDB:
            numRecorded = len(responseDB[contestant])
        else:
            numRecorded = 0
        if responseNum>numRecorded:
            return sopN(f'Failed! You have only sent [{str(numRecorded)}] response{{/s}} so far, not {str(responseNum)}!')
        responseDB[contestant][responseNum-1] = {'content':newResponse,'ID':messageID}
        updateResponseDB(responseDB)
        message = 'Success! Your '
        if maxResponses(contestant)!=1:
            message += f'#{str(responseNum)} '
        message += f'response now reads:\n`{newResponse}`'
    return message

def removeResponse(contestant,responseNum):
    if responseNum<1:
        return ("Failed! A contestant can't have less than 1 response, silly!","")
    with updateDBLock:
        responseDB = getResponseDB()
        if contestant in responseDB:
            numRecorded = len(responseDB[contestant])
            if responseNum>numRecorded:
                return (sopN(f'Failed! That contestant has only sent [{str(numRecorded)}] response{{/s}} so far!'),"")
            responseContent = responseDB[contestant][responseNum-1]['content']
            responseDB[contestant].pop(responseNum-1)
            if numRecorded==1:
                del responseDB[contestant]
        else:
            return ("Failed! That contestant isn't in the responding database!","")
        updateResponseDB(responseDB)
    return (f"Success! Response `{responseContent}` was removed. The contestant's response count is now {str(numRecorded-1)}.",
            responseContent)
    

def viewResponses(contestant):
    responseDB = getResponseDB()
    # make sure the contestant has sent at least one response
    if contestant not in responseDB:
        return "Error! You have not sent any responses!"
    userResponses = responseDB[contestant]
    message = "Here's a list of your responses:"
    for response in userResponses:
        message += f"\n`{response["content"]}`"
    return message

def startResponding():
    with updateDBLock:
        seasonInfoDB = getSeasonInfoDB()
        seasonInfoDB['currentDNPs'] = []
        currentRound = seasonInfoDB['currentRound']
        createResponseDB()
        prompt = seasonInfoDB['prompts'][-1]
        seasonInfoDB['period'] = 'responding'
        message = (f"Round {str(currentRound)} has started! Your prompt is: \n"+
                        f"```{prompt}```")
        limitType = {'char':'characters','word':'words'}[seasonInfoDB['limitType']]
        limit = str(seasonInfoDB['limit'])
        message += f"Your response must not exceed **{limit} {limitType}**, or it will be rejected."
        deadline = None
        if seasonInfoDB['deadlineMode']=='min':
            deadline = addMinutes(datetime.now().timestamp(),seasonInfoDB['deadlineLen'])
            message += f'\nRespond by <t:{deadline}:T>, which is <t:{deadline}:R>.'
        elif seasonInfoDB['deadlineMode']=='day':
            deadline = addDays(datetime.now().timestamp(),seasonInfoDB['deadlineLen'])
            message += f'\nRespond by <t:{deadline}:F>, which is <t:{deadline}:R>.'
        seasonInfoDB['deadline'] = deadline
        updateSeasonInfoDB(seasonInfoDB)
    return (message, "prompts")

def closeResponding():
    seasonInfoDB = getSeasonInfoDB()
    period = seasonInfoDB['period']
    if period != 'responding':
        return (f"Error! Current period is {period}!", None, None)
    print("attempting closeResponding")
    with updateDBLock:
        seasonInfoDB = getSeasonInfoDB()
        seasonInfoDB['period'] = 'preVoting'
        seasonInfoDB['deadline'] = None
        # get the number of responses sent 
        responseDB = getResponseDB()
        messagesAsKeys = userKeysToMessageKeys(responseDB)
        responseCount = len(messagesAsKeys)
        seasonInfoDB['numResponses'] = responseCount
        # eliminate people if they didn't send a response
        DNPs = []
        for aliveContestant in seasonInfoDB['aliveContestants']:
            if aliveContestant not in responseDB:
                DNPs.append(aliveContestant)
        if len(DNPs)!=0:
            # eliminate DNPs if vanilla; otherwise, add them to a list to give them 0% SR later
            DNPDisplayNames = []
            for DNP in DNPs:
                DNPDisplayNames.append(seasonInfoDB['aliveContestants'][DNP]['displayName'])
                elimFormat = seasonInfoDB['elimFormat']
                if elimFormat == 'vanilla':
                    seasonInfoDB['eliminatedContestants'][DNP] = seasonInfoDB['aliveContestants'][DNP]
                    del seasonInfoDB['aliveContestants'][DNP]
                # if statement in case of running code multiple times
                elif DNP not in seasonInfoDB['currentDNPs']:
                    seasonInfoDB['currentDNPs'].append(DNP)
        updateSeasonInfoDB(seasonInfoDB)
    currentRound = seasonInfoDB['currentRound']
    message = (f"Round {str(currentRound)} responding is now closed!\n"+
               f"We received {str(responseCount)} responses from {str(len(responseDB))} contestants.")
    if seasonInfoDB['currentRound']!=1:
        if len(DNPs)==0:
            message += ("\nAll contestants sent responses. Hooray!")
        else:
            message += ("\n"+sopL(f"{lts(DNPDisplayNames)} ") 
                        +"failed to send responses. So sad.")
    return (message,'prompts',DNPs)



    
    

