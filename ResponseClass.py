import re

class Response:
    def __init__(self,contents):
        self.contents = contents
        self.votescores = []
        self.rawscore = 0
        self.techscore = 0

    def edit(self,contents):
        self.contents=contents

    def rawScore(self):
        self.rawscore = sum(self.votescores)/len(self.votescores)

    def addVoteScore(self,votescore):
        self.votescores.append(votescore)

    def wordCount(self):
        return len(re.split('\s+(?=\S)',self.contents))
