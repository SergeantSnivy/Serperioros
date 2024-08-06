import csv
from SeasonInfo import getSeasonInfoDB, updateSeasonInfoDB, getSeasonName
from statistics import pstdev
from scipy.stats import norm
import gspread
import PrivateStuff as priv
from gspread.utils import ValueInputOption
from googleapiclient.discovery import build

StatsInfo = {'Percentiles': (lambda rows: getPercentilePairs(rows), 'float'),
             'SRs': (lambda rows: getSRPairs(rows), 'float'),
             'StDev': (lambda rows: getStDevPairs(rows), 'float'),
             'Verbosity': (lambda rows: getVerbosityPairs(rows), 'int')}
StatsFileName = lambda stat: getSeasonName()+stat+".csv"

def removeNonCountingResponses(statsRows):
    onlyCountingResponses = []
    contestantNames = [row[0] for row in statsRows]
    for i,row in enumerate(statsRows):
        if row[0] not in contestantNames[:i]:
            onlyCountingResponses.append(row)
    return onlyCountingResponses

def CSVToArray(CSVFileName):
    outerArray = []
    with open(CSVFileName, newline='',encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
        for row in reader:
            outerArray.append(row)
    return outerArray

def ArrayToCSV(CSVFileName,array):
    with open(CSVFileName, 'w', newline='',encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter='\t', dialect='excel',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in array:
            writer.writerow(row)

def createStatsSheets():
    seasonInfoDB = getSeasonInfoDB()
    statArray = []
    headerRow = ["#","Contestant","Total","Average","St. Dev"]
    statArray.append(headerRow)
    contestantNames = [seasonInfoDB['aliveContestants'][contestant]['displayName'] 
                       for contestant in seasonInfoDB['aliveContestants']]
    for i,contestant in enumerate(contestantNames):
            statArray.append([str(i+1),contestant,0,0,0])
    for stat in StatsInfo:
        statFileName = StatsFileName(stat)
        ArrayToCSV(statFileName,statArray)
    ArrayToCSV(StatsFileName('EveryResponse'),[["#","Rd#","Contestant","Response","Score","St. Dev","Skew"]])

# stats rows format: contestant, response, score, stdev, skew

def getPercentilePairs(statsRows):
    return [(row[0],row[2]) for row in statsRows]

def getSRPairsFromContestantScorePairs(contestantScorePairs):
    allScores = [pair[1] for pair in contestantScorePairs]
    mean = sum(allScores)/len(allScores)
    stdev = pstdev(allScores)
    SRPairs = []
    for userID, currentScore in contestantScorePairs:
        SRPairs.append((userID,norm.cdf(currentScore,mean,stdev)))
    return SRPairs

def getSRPairs(statsRows):
    allScores = [row[2] for row in statsRows]
    mean = sum(allScores)/len(allScores)
    stdev = pstdev(allScores)
    SRPairs = []
    for row in statsRows:
        SRPairs.append((row[0],norm.cdf(row[2],mean,stdev)))
    return SRPairs

def getStDevPairs(statsRows):
    return [(row[0],row[3]) for row in statsRows]

def getVerbosityPairs(statsRows):
    return [(row[0],len(row[1])) for row in statsRows]

# floats will be written in the sheet as a percent
# ints will be written in the sheet as an int
def toNum(numStr,numType):
    if numType=='int':
        return int(numStr)
    elif numType=='float':
        return float(numStr)
    else:
        print("Invalid num type")

def toPercent(num):
    return str(num*100)+"%"

def updateStatFile(CSVFileName,newPairs,numType):
    headerRow = ("#","Contestant","Total","Average","St. Dev")
    iTotal, iAvg, iStdev = [headerRow.index(stat) for stat in ["Total","Average", "St. Dev"]]
    print('\n')
    print(CSVFileName)
    statsArray = CSVToArray(CSVFileName)
    #print(statsArray)
    contestantsInFile = [row[1] for row in statsArray]
    # add new round to header
    statsArray[0].append("Round "+str(len(statsArray[0][5:])+1))
    debuts = []
    # find each contestant's position in the stats sheet and then append their newest value
    for i,pair in enumerate(newPairs):
        #print(pair)
        if pair[0] in contestantsInFile:
            statsFilePos = contestantsInFile.index(pair[0])
        else:
            debuts.append(pair)
            continue
        currentRow = statsArray[statsFilePos]
        currentRow.append(pair[1])
        # recalcuclate total, average, stdev
        #print(currentRow)
        allValues = [toNum(value,numType) for value in currentRow[5:]]
        print(allValues)
        print("Pstdev time")
        currentRow[iTotal] = sum(allValues)
        currentRow[iAvg] = sum(allValues)/len(allValues)
        currentRow[iStdev] = pstdev(allValues)
    # add debuts
    for contestant, value in debuts:
        statsArray.append([0]*len(statsArray)[0])
        currentRow = statsArray[-1]
        currentRow[1] = contestant
        currentRow[iTotal] = value
        currentRow[iAvg] = value
        currentRow[-1] = value
    #print(statsArray)
    statsArray = [statsArray[0]]+sorted(statsArray[1:],reverse=True,key=lambda x: float(x[2]))
    # redo ranks, convert all values to numbers so it plays nice with sheets
    for i,row in enumerate(statsArray[1:]):
        row[0] = i+1
        for i in range(2,len(row)):
            # account for non-int average/stdev on a stat where data type is int
            if i==iAvg or i==iStdev:
                row[i] = toNum(row[i],"float")
            else:
                row[i] = toNum(row[i],numType)
    print(statsArray)
    '''if numType == "float":
        for row in statsArray[1:]:
            row[2:] = [toPercent(value) for value in row[2:]]'''
    ArrayToCSV(CSVFileName,statsArray)
    return statsArray

def updateEveryResponseFile(CSVFileName,newRows):
    currentRound = getSeasonInfoDB()['currentRound']
    everyResponseArray = CSVToArray(CSVFileName)
    for row in newRows:
        everyResponseArray.append([None,currentRound]+list(row))
    #print(everyResponseArray)
    everyResponseArray = [everyResponseArray[0]]+sorted(everyResponseArray[1:],reverse=True,key=lambda x: float(x[4]))
    #print(everyResponseArray)
    # redo ranks, convert all values to numbers so it plays nice with sheets
    for i,row in enumerate(everyResponseArray[1:]):
        print(row[0])
        row[0] = i+1
        for i in range(4,len(row)):
            row[i] = toNum(row[i],"float")
    print(everyResponseArray)
    ArrayToCSV(CSVFileName,everyResponseArray)
    return everyResponseArray

def createSeasonGoogleSheet():
    client = gspread.authorize(priv.creds)
    rV = client.copy(priv.stats_template_id,title=f"{getSeasonName()} Stats Sheet")
    for email in priv.my_emails:
        rV.share(email,perm_type='user',role='writer')
    rV.share('',perm_type='anyone',role='reader')
    seasonInfoDB = getSeasonInfoDB()
    seasonInfoDB['statsSheetID'] = rV.id
    updateSeasonInfoDB(seasonInfoDB)
    
def updateGoogleSheet(statsArrays):
    statsSheetID = getSeasonInfoDB()['statsSheetID']
    client = gspread.authorize(priv.creds)
    rV = client.open_by_key(statsSheetID)
    for n,currentArray in enumerate(statsArrays):
        try:
            worksheet = rV.get_worksheet(n)
            worksheet.resize(rows=len(currentArray), cols=len(currentArray[0]))
        except:
            worksheet = rV.add_worksheet(title=f"Section {str(n)}", rows=len(currentArray), cols=len(currentArray[0]))
        print(currentArray)
        worksheet.update(currentArray,value_input_option=ValueInputOption.user_entered)
    return rV.id

def updateAllStats(newRows):
    currentRound = getSeasonInfoDB()['currentRound']
    print('ok-1')
    if currentRound==1:
        createStatsSheets()
        print('ok-0.5')
        createSeasonGoogleSheet()
    allStatsArrays = []
    print('ok0')
    onlyCountingRows = removeNonCountingResponses(newRows)
    print(onlyCountingRows)
    print('ok')
    for stat in StatsInfo:
        statFileName = StatsFileName(stat)
        statNewData = StatsInfo[stat][0](onlyCountingRows)
        statArray = updateStatFile(statFileName,statNewData,StatsInfo[stat][1])
        allStatsArrays.append(statArray)
    everyResponseArray = updateEveryResponseFile(StatsFileName('EveryResponse'),newRows)
    allStatsArrays.append(everyResponseArray)
    return updateGoogleSheet(allStatsArrays)

def removeMostRecentRoundFromStatFile(CSVFileName):
    statsArray = CSVToArray(CSVFileName)
    firstRowLen = len(statsArray[0])
    for i,row in enumerate(statsArray):
        if len(row)==firstRowLen:
            statsArray[i] = row[:firstRowLen-1]
    ArrayToCSV(CSVFileName,statsArray)
    return statsArray
    
def removeMostRecentRoundFromEveryResponseFile(CSVFileName):
    everyResponseArray = CSVToArray(CSVFileName)
    currentRound = getSeasonInfoDB()['currentRound']
    newEveryResponseArray = [everyResponseArray[0]]
    i=1
    while i<len(everyResponseArray):
        currentRow = everyResponseArray[i]
        newEveryResponseArray.append(currentRow)
        # duplicate entries will be consecutive, so just increment the index by an extra 1 to skip the duplicate
        currentRowRound = int(currentRow[1])
        if currentRound==currentRowRound:
            i += 1
        i += 1
    ArrayToCSV(CSVFileName,newEveryResponseArray)
    return newEveryResponseArray

def removeMostRecentRoundFromAllStats():
    allStatsArrays = []
    for stat in StatsInfo:
        statFileName = StatsFileName(stat)
        statArray = removeMostRecentRoundFromStatFile(statFileName)
        allStatsArrays.append(statArray)
    everyResponseArray = removeMostRecentRoundFromEveryResponseFile(StatsFileName('EveryResponse'))
    allStatsArrays.append(everyResponseArray)
    return updateGoogleSheet(allStatsArrays)







