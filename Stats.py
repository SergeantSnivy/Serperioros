import csv
from SeasonInfo import seasonName, getSeasonInfoDB, updateSeasonInfoDB
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
StatsFileName = lambda stat: seasonName+stat

def removeNonCountingResponses(statsRows):
    onlyCountingResponses = []
    contestantNames = [row[0] for row in statsRows]
    for i,row in enumerate(statsRows):
        if row[0] not in contestantNames[i+1]:
            onlyCountingResponses.append(row)
    return onlyCountingResponses

def CSVToArray(CSVFileName):
    outerArray = []
    with open(CSVFileName, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter='\t', quotechar='|')
        for row in reader:
            outerArray.append(row)
    return outerArray

def ArrayToCSV(CSVFileName,array):
    with open(CSVFileName, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter='\t', dialect='excel',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in array:
            writer.writerow(row)

def createStatsSheets():
    seasonInfoDB = getSeasonInfoDB()
    statArray = []
    statArray.append(["#","Contestant","Total","Average","St. Dev"])
    contestantNames = [contestant['displayName'] for contestant in seasonInfoDB['aliveContestants']]
    for i,contestant in enumerate(contestantNames):
            statArray.append([str(i+1),contestant,0,0,0])
    for stat in StatsInfo:
        statFileName = StatsFileName(stat)
        ArrayToCSV(statFileName,statArray)
    ArrayToCSV(StatsFileName('EveryResponse'),[])

# stats rows format: contestant, response, score, stdev, skew

def getPercentilePairs(statsRows):
    return [(row[0],row[2]) for row in statsRows]

def getSRPairs(statsRows):
    allScores = [row[2] for row in statsRows]
    mean = sum(allScores)/len(allScores)
    stdev = pstdev(allScores)
    SRPairs = []
    for row in statsRows:
        SRPairs.append((row[0],norm.cdf(row[2],mean,stdev)))
    return statsRows

def getStDevPairs(statsRows):
    return [(row[0],row[3]) for row in statsRows]

def getVerbosityPairs(statsRows):
    return [(row[0],len(row[1])) for row in statsRows]

def toNum(numStr,numType):
    if numType=='int':
        return int(numStr)
    elif numType=='float':
        return float(numStr)
    else:
        print("Invalid num type")

def updateStatFile(CSVFileName,newPairs,numType):
    statsArray = CSVToArray(CSVFileName)
    contestantsInFile = [row[0] for row in statsArray]
    # add new round to header
    statsArray[0].append("Round "+str(len(statsArray[0][5:])+1))
    # find each contestant's position in the stats sheet and then append their newest value
    for i,pair in enumerate(newPairs):
        statsFilePos = contestantsInFile.index(pair[0])
        currentRow = statsArray[statsFilePos]
        currentRow.append(str(pair[1]))
        # recalcuclate total, average, stdev
        allValues = [toNum(value,numType) for value in currentRow[5:]]
        currentRow[2] = str(sum(allValues))
        currentRow[3] = str(sum(allValues)/len(allValues))
        currentRow[4] = str(pstdev(allValues))
    statsArray.sort(reverse=True,key=lambda x: toNum(x[2],numType))
    ArrayToCSV(CSVFileName,statsArray)
    return statsArray

def updateEveryResponseFile(CSVFileName,newRows):
    everyResponseArray = CSVToArray(CSVFileName)
    for row in newRows:
        everyResponseArray.append([None]+row)
    everyResponseArray.sort(reverse=True,key=lambda x: float(x[2]))
    for i,row in enumerate(everyResponseArray):
        row[0] = i+1
    ArrayToCSV(CSVFileName,everyResponseArray)
    return everyResponseArray

def createSeasonGoogleSheet():
    client = gspread.authorize(priv.creds)
    rV = client.copy(priv.results_template_id,title=f"{seasonName} Stats Sheet")
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
        worksheet.update(currentArray)
    return rV.id

def updateAllStats(newRows):
    currentRound = getSeasonInfoDB()['currentRound']
    if currentRound==1:
        createStatsSheets()
        createSeasonGoogleSheet()
    allStatsArrays = []    
    onlyCountingRows = removeNonCountingResponses(newRows)
    for stat in StatsInfo:
        statFileName = StatsFileName(stat)
        statNewData = StatsInfo[stat][0](onlyCountingRows)
        statArray = updateStatFile(statFileName,statNewData,StatsInfo[stat][1])
        allStatsArrays.append(statArray)
    everyResponseArray = updateEveryResponseFile(StatsFileName('EveryResponse'),newRows)
    allStatsArrays.append(everyResponseArray)
    updateGoogleSheet()



