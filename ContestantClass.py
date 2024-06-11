from ResponseClass import Response

class Contestant:
    def __init__(self,username):
        self.username = username
        self.alive=True
        self.pastResponses = []
        self.currentResponses = []
        self.pastTechnicals = []
        self.currentTechnicals = []
        self.allottedResponses = 1
        self.allottedTechnicals = 1

    def eliminate(self):
        self.alive=False
        self.allottedResponses = 0
        self.allotedTechnicals = 0

    def giveDRP(self):
        self.allottedResponses = 2

    def giveTTP(self):
        self.allottedTechnicals = 3

    def resetAllotted(self):
        self.allottedResponses = 1
        self.allottedTechnicals = 1

    def currentToPast(self):
        for response in self.currentResponses:
            self.pastResponses.append(response)
        self.currentResponses = []
        for technical in self.currentTechnicals:
            self.pastTechnicals.append(technical)
        self.currentTechnicals = []

    def recordResponse(self,responseContents):
        message = ''
        if len(self.currentResponses)>=self.allottedResponses:
            message+="Error: You cannot submit more than "
            if self.allottedResponses==1:
                message+=("1 response! To edit your response, use "+
                          "`sp!edit [new response here]`").
            else:
                num = str(self.allottedResponses)
                message+=("{num} responses! To edit a response, use "+
                          "`sp!edit [number of response] [new response here].")

            return message
        recordedResponse = Response(responseContents)
        self.currentResponses.append(recordedResponse)
        message+=("Success! Your response has been recorded as: \n"+
                  "`{responseContents}`\n")
        wordCount = recordedResponse.wordCount
        message+=(f"Your response's word count is: {str(wordCount)}\n")
        if wordCount > 10:
            message+=("WARNING: Your response exceeds the word limit! "+
                      "It will be marked as such in voting!\n")
        message+=("Edit this response at any time by using "+
                  "`sp!edit ")
        if len(self.currentResponses)>1:
            num = str(len(currentResponses))
            message+=num+" "
        message+="[new response here]`."
        return message
        
