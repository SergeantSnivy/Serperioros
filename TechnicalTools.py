import re

def reformat(response:str):
    # replace newlines 
    response = re.sub('\n',' ',response)
    # replace tabs (stats sheet delimiter)
    response = re.sub('\t',' ',response)
    return response
)
def getWords(response:str):
    return re.split('\s+',response)