import gspread
from gspread_formatting import *
from gspread.utils import ValueInputOption, rowcol_to_a1
from googleapiclient.discovery import build
from urllib.parse import quote
from random import shuffle
import math
from copy import deepcopy
import numpy as np
import pandas as pd
import PrivateStuff as priv
from SeasonInfo import getSeasonInfoDB, getSeasonName

thickBlackBorder = Border(style="SOLID_THICK")
regularText = TextFormat(fontFamily="Trebuchet MS",fontSize=11)
keywordText = TextFormat(fontFamily="Trebuchet MS",fontSize=14,bold=True)
keywordColor = ColorStyle(rgbColor=Color(0.902, 0.569, 0.22))
keywordCell = CellFormat(backgroundColorStyle=keywordColor,textFormat=keywordText,
                         borders=Borders(top=thickBlackBorder,bottom=thickBlackBorder,
                                         left=thickBlackBorder,right=thickBlackBorder))
keyletterColor = ColorStyle(rgbColor=Color(0.494, 0.82, 0.349))
keyletterCell = CellFormat(backgroundColorStyle=keyletterColor,textFormat=regularText)
responseColors = (ColorStyle(rgbColor=Color(1, 0.949, 0.8)),ColorStyle(rgbColor=Color(1, 0.918, 0.671)))
responseCells = (CellFormat(backgroundColorStyle=responseColors[0],textFormat=regularText),
                 CellFormat(backgroundColorStyle=responseColors[1],textFormat=regularText))

def surroundRangeWithBorders(formatGrid:list[list[CellFormat]],topLeftRow:int,topLeftCol:int,width:int,height:int):
    # create border object for every cell
    for i in range(width):
        for j in range(height):
            formatGrid[topLeftRow+j][topLeftCol+i].borders = Borders()
    # add top/bottom borders
    for i in range(width):
        formatGrid[topLeftRow][topLeftCol+i].borders.top=thickBlackBorder
        formatGrid[topLeftRow+height-1][topLeftCol+i].borders.bottom=thickBlackBorder
    # add left/right borders
    for j in range(height):
        formatGrid[topLeftRow+j][topLeftCol].borders.left=thickBlackBorder
        formatGrid[topLeftRow+j][topLeftCol+width-1].borders.right=thickBlackBorder

# gets all Unicode characters that will be used as keyletters
def getUniTable(numResponses):
    uniTable = []
    # in order: upper letters, lower letters, digits, then other latin letters
    uniRanges = [(65,91),(97,123),(48,58)]
    for r in uniRanges:
        for i in range(r[0],r[1]):
            uniTable.append(chr(i))
            if len(uniTable)>=numResponses:
                return uniTable
    numLeft = numResponses-len(uniTable)
    for i in range(192,192+numLeft):
        uniTable.append(chr(i))
    return uniTable

def screenToVotelink(keyword,prompt,screen):
    urlStart = "https://voter.figgyc.uk/#votelink3="
    urlRest = ""
    urlRest += f"{keyword}\t{prompt}\t"
    for letter,response in screen:
        # undo sanitization if it occurred
        if response[:2] in ("'+","'=","''"):
            print("Changing "+response)
            response = response[1:]
        print(response)
        urlRest += f"{letter}\t{response}\n"
    # get rid of extra newline
    urlRest = urlRest[:-1]
    return urlStart+quote(urlRest,safe='')


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
    formatGrid = [(None,None)]
    sectionName = chr(65+sectionNum)
    responsesOnScreen = {}
    keywordsInSection = {sectionName: []}
    currentRow = 1
    for j in range(len(splits)):
        keyword = f'{chr(65+sectionNum)}{str(j+1)}'
        responsesOnScreen[keyword]={}
        keywordsInSection[sectionName].append(keyword)
        keyResponsePairs.append((None,keyword))
        formatGrid.append((None,deepcopy(keywordCell)))
        currentRow += 1
        topRowOfPairs = currentRow
        numLetters = len(splits[j])
        for k,ID in enumerate(splits[j],start=0):
            response = responses[ID]['content']
            # sanitize formulas
            if response[0] in ['=','+',"'"]:
                response = "'" + response
            keyResponsePairs.append((uniTable[k],response))
            formatGrid.append((deepcopy(keyletterCell),deepcopy(responseCells[currentRow%2])))
            responsesOnScreen[keyword][uniTable[k]] = ID
            currentRow += 1
        # add borders
        surroundRangeWithBorders(formatGrid,topRowOfPairs,0,1,numLetters)
        surroundRangeWithBorders(formatGrid,topRowOfPairs,1,1,numLetters)
        # add votelink
        keyResponsePairs[topRowOfPairs-1] = (None,f'''=HYPERLINK("{
            screenToVotelink(keyword,prompt,keyResponsePairs[topRowOfPairs:currentRow])}","{keyword}")''')
        if j<len(splits)-1:
            keyResponsePairs.append((None,None))
            formatGrid.append((None,None))
            currentRow += 1
    return keyResponsePairs,responsesOnScreen,keywordsInSection,formatGrid

# takes all the sections and puts them into an Excel sheet (irrelevant)
'''def fill_excel_sheet(file_path,sections):
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        for n,sec in enumerate(sections):
            currentDF = pd.DataFrame(sec)
            currentDF = currentDF.fillna('')
            currentDF.to_excel(writer,sheet_name=f'Section {str(n+1)}',index=False,
                               header=None,engine_kwargs={'options': {'strings_to_formulas': True}})'''

# imports data from 2d array into a Google Sheet
# the Google Sheet will be formatted based on a voting template
def create_google_sheet(sections,currentRound):
    client = gspread.authorize(priv.creds)
    rV = client.copy(priv.voting_template_id,title=f"{getSeasonName()} Round {str(currentRound)} Voting")
    for email in priv.my_emails:
        rV.share(email,perm_type='user',role='writer')
    rV.share('',perm_type='anyone',role='reader')
    print
    #df = pd.read_excel(file_path,sheet_name=None,header=None,na_filter=False)
    for n,(currentSecValues,currentFormatGrid) in enumerate(sections):
        try:
            worksheet = rV.get_worksheet(n)
            worksheet.resize(rows=len(currentSecValues), cols=len(currentSecValues[0]))
        except:
            worksheet = rV.add_worksheet(title=f"Section {str(n)}", rows=len(currentSecValues), cols=len(currentSecValues[0]))
        worksheet.update(currentSecValues,value_input_option=ValueInputOption.user_entered)
        # create cellname/cellformat pairs
        nameFormatPairs = []
        for row in range(len(currentFormatGrid)):
            for col in range(len(currentFormatGrid[0])):
                if currentFormatGrid[row][col]:
                    nameFormatPairs.append((rowcol_to_a1(row+1,col+1),currentFormatGrid[row][col]))
        format_cell_ranges(worksheet,nameFormatPairs)
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
            keyResponsePairs,newScreens,keywordsInSection,sectionFormatGrid = generate_section(responses,numScreens,len(sections))
            sections.append((keyResponsePairs,sectionFormatGrid))
            allScreens = allScreens | newScreens
            keywordsInEachSection = keywordsInEachSection | keywordsInSection
    sheet_id = create_google_sheet(sections,currentRound)
    print(sheet_id)
    return uniTable,allScreens,keywordsInEachSection,sheet_id