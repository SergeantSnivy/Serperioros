import re

def listToString(itemList):
    listAsString = '['
    for i in range(len(itemList)-1):
        listAsString += str(itemList[i])+','
    listAsString += str(itemList[-1])+']'
    return listAsString

def singularOrPluralFromList(messageString):
    itemListString = re.findall('\[(.*)\]',messageString)[0]
    itemList = itemListString.split(',')
    listReplacement = f'`{itemList[0]}`'
    if len(itemList)==1:
        wordReplacement = r'\1'
    else:
        wordReplacement = r'\2'
        if len(itemList)==2:
            listReplacement += f' and `{itemList[1]}`'
        else:
            listReplacement += ', '
            for i in range(1,len(itemList)-1):
                listReplacement += f'`{itemList[i]}`, '
            listReplacement += f'and `{itemList[-1]}`'
    messageString = re.sub(f'\[{re.escape(itemListString)}\]',listReplacement,
                           messageString)
    messageString = re.sub('{(.*?)/(.*?)}',wordReplacement,messageString)
    return messageString

def singularOrPluralFromNumber(messageString):
    number = int(re.findall('\[(.*)\]',messageString)[0])
    if number==1:
        wordReplacement = r'\1'
    else:
        wordReplacement = r'\2'
    messageString = re.sub(f'\[{str(number)}\]',str(number),
                           messageString)
    messageString = re.sub('{(.*?)/(.*?)}',wordReplacement,messageString)
    return messageString

def sheetsRowArray(array):
    arrayStr = str(array)
    return '{'+str(array)[1:len(arrayStr)-1]+'}'
    
