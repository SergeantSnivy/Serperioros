import re

def reformat(response:str):
    # replace newlines 
    response = re.sub('\n',' ',response)
    return response

def getWords(response:str):
    return re.split('\s+',response)