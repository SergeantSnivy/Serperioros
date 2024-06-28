import gspread
from gspread.utils import ValueInputOption
from googleapiclient.discovery import build
from random import shuffle
import math
import numpy as np
import pandas as pd
import PrivateStuff as priv
from SeasonInfo import getSeasonInfoDB

# gets all Unicode characters that will be used as keyletters
def getUniTable(numResponses):
    uniTable = []
    uniRanges = [(65,91),(97,123),(48,61),(62,65)]
    for r in uniRanges:
        for i in range(r[0],r[1]):
            uniTable.append(chr(i))
            if len(uniTable)>=numResponses:
                return uniTable
    numLeft = numResponses-len(uniTable)
    for i in range(161,161+numLeft):
        uniTable.append(chr(i))
    return uniTable

# generates a voting section based on a provided number of screens
# returns a dictionary with all responses on a screen per its keyword...
# ...a list of all rows of data to put in the section's Excel worksheet...
# ...and a dictionary with the section name as a key and a list of the keywords as the value
def generate_section(responses,numScreens,sectionNum):
    # responses is a dict, so get all the keys in a list
    IDs = [ID for ID in responses]
    shuffle(IDs)
    splits = np.array_split(IDs,numScreens)
    keyResponsePairs = [(None,prompt)]
    sectionName = chr(65+sectionNum)
    responsesOnScreen = {}
    keywordsInSection = {sectionName: []}
    for j in range(len(splits)):
        keyword = f'{chr(65+sectionNum)}{str(j+1)}'
        responsesOnScreen[keyword]={}
        keywordsInSection[sectionName].append(keyword)
        keyResponsePairs.append((None,keyword))
        for k,ID in enumerate(splits[j],start=0):
            keyResponsePairs.append((uniTable[k],responses[ID]['content']))
            responsesOnScreen[keyword][uniTable[k]] = ID
        if j<len(splits)-1:
            keyResponsePairs.append((None,None))
    return keyResponsePairs,responsesOnScreen,keywordsInSection

# takes all the sections and puts them into an Excel sheet (irrelevant)
'''def fill_excel_sheet(file_path,sections):
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        for n,sec in enumerate(sections):
            currentDF = pd.DataFrame(sec)
            currentDF = currentDF.fillna('')
            currentDF.to_excel(writer,sheet_name=f'Section {str(n+1)}',index=False,
                               header=None,engine_kwargs={'options': {'strings_to_formulas': True}})'''

# imports data from Excel sheet into a Google Sheet
# the Google Sheet will be formatted based on a voting template
def create_google_sheet(sections):
    client = gspread.authorize(priv.creds)
    rV = client.copy(priv.voting_template_id,title="Testing")
    for email in priv.my_emails:
        rV.share(email,perm_type='user',role='writer')
    rV.share('',perm_type='anyone',role='reader')
    print
    #df = pd.read_excel(file_path,sheet_name=None,header=None,na_filter=False)
    for n,currentSec in enumerate(sections):
        try:
            worksheet = rV.get_worksheet(n+1)
            worksheet.resize(rows=len(currentSec), cols=len(currentSec[0]))
        except:
            worksheet = rV.add_worksheet(title=f"Section {str(n)}", rows=len(currentSec), cols=len(currentSec[0]))
        worksheet.update(currentSec)
    return rV.id

# does all that stuff in order to get the final voting Google Sheet
# returns the sheet ID, as well as the list of keyletters and the keyword-response dictionary
def generate_voting(responses):
    numResponses=len(responses)
    global uniTable
    uniTable = getUniTable(numResponses)
    sectionSpecs = []
    # maxes = [-1,50,30,20,10]
    maxes = [-1,50,30,12,6]
    repeats = [1,2,2,2,3]
    for i in range(5):
        sectionSpecs.append({'maxPerScreen':maxes[i],'repeat':repeats[i]})
    sections = []
    seasonInfoDB = getSeasonInfoDB()
    currentRound = seasonInfoDB['currentRound']
    global prompt
    prompt = seasonInfoDB['prompts'][currentRound-1]
    allScreens = {}
    keywordsInEachSection = {}
    for spec in sectionSpecs:
        # get number of screens
        if spec['maxPerScreen']==-1:
            numScreens=1
        else:
            numScreens = math.ceil(len(responses)/spec['maxPerScreen'])
        for i in range(spec['repeat']):
            keyResponsePairs,newScreens,keywordsInSection = generate_section(responses,numScreens,len(sections))
            sections.append(keyResponsePairs)
            allScreens = allScreens | newScreens
            keywordsInEachSection = keywordsInEachSection | keywordsInSection
    sheet_id = create_google_sheet(sections)
    print(sheet_id)
    return uniTable,allScreens,keywordsInEachSection,sheet_id