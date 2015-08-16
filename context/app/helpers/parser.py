import json
import re
import os

from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService
 
class Parser:
    """Takes in Message JSON object from API and returns requested attributes"""

    def __init__(self):
        # NB This was only tested in GMAIL, we don't know if the thread msg header format is uniform
        # NB Have to extend pattern to include support for foreign language
        #threadHeaderRegExp = re.compile(r'On\s(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s[A-Z]?[a-z]{2,3}\s[0-9]{1,2},\s[0-9]{4}\sat\s[0-9]{1,2}:[0-9]{2}\s(?:AM|PM),\s[^<]+<[^@]+@[^>]+>\swrote:')
        self.threadHeaderRegExp = re.compile(r'On\s(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s[A-Z]?[a-z]{2,3}\s[0-9]{1,2},\s[0-9]{4}\sat\s[0-9]{1,2}:[0-9]{2}\s(?:AM|PM),\s[^<]+<[^@]+@[^>]+>\swrote:')                    
       
        self.toneAnalyzer = ToneAnalyzerService(os.getenv("VCAP_SERVICES"))
        self.personalityAnalyzer = PersonalityInsightsService(os.getenv("VCAP_SERVICES"))

        self.output = {} # dictionary so we can convert to JSON
        self.personality = {} # store specific personality traits and score
        
    def extractMessage(self, msg):
        """Helper function for getMsgBodyList to get only the FIRST message in thread"""
        """NB we don't need other messages because they have their own message id"""   
        iterator = self.threadHeaderRegExp.finditer(msg)
        offset = -1
        cleanMsg = ''
        for m in iterator:
            offset = m.start()
            break
        if offset > 0:
            cleanMsg = msg[0:offset-1]
            cleanMsg = cleanMsg.strip()
        else:
            cleanMsg = msg
        return cleanMsg

    def getBig5(self, personality):
        children = personality['tree']['children']['children']
        for child in children:
            self.personality[(child['id'])] = child['percentage']
        return
           

    def analyzeMessages(self, msgs, **params):
        self.output = {}
        getTone = params['tone']
        message = {} 
        msgList = []
        msgContentList = []
        allContent = '\n'   
        for m in msgs:
            if m.get(include_body=1, body_type='text/plain') == False:
                continue
            message['datetime'] = m.date 
            message['subject'] = m.subject
            message['to'] = params['to']
            message['from'] = params['from_'] 
            for mInfo in m.body:
                content = self.extractMessage(mInfo['content'])
                message['content'] = content
                msgContentList.append(content)
                message['tone'] = json.dumps(self.toneAnalyzer.getTone(content.encode('utf-8')))
                # to do get average message
                # aggregate message content
                allContent = allContent + content
            msgList.append(message)
        if params['personality'] == True and len(allContent) > 4000:
            personalityJson = self.personalityAnalyzer.getProfile(allContent)
            getBig5(json.loads(personalityJson))
        #getPersonInfo()
        return msgContentList

    #def getPersonInfo(self)




