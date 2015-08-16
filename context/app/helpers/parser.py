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
        self.personality = []
        children = personality['tree']['children']['children']
        for child in children:
            self.personality[(child['id'])] = child['percentage']
        return
           

    def analyzeMessages(self, msgs, **params):
        rootJson = {}
        rootJson['email'] = params['from_']
        rootJson['numberOfEmails'] = len(msgs)
        isContact = False
        if params['type_'] == 'contact':
            isContact = True 
        self.output = {}
        message = {} 
        emailMessages = []
        msgContentList = []
        allContent = '\n'   
        toneSum = 0
        toneTracking = []
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
                toneJson = self.toneAnalyzer.getTone(content.encode('utf-8'))
                message['tone'] = json.dumps(toneJson)
                toneAve = self.extractToneAverage(toneJson)
                toneTracking.append(toneAve)
                toneSum = toneSum + toneAve

                # to do get average message
                # aggregate message content
                allContent = allContent + content
            emailMessages.append(message)
        if len(allContent) > 4000 and params['personality'] == True:
            personalityJson = self.personalityAnalyzer.getProfile(allContent)
            getBig5(json.loads(personalityJson))
            rootJson['personality'] = self.personality
        if params['type_'] == 'masterUser':
            rootJson['emailMessages'] = emailMessages
        if isContact:
            rootJson['avgTone_msgsFromContact'] = toneSum / len(msgs)
            rootJson['toneTracking_msgsFromContact'] = toneTracking[:5]
        else:
            rootJson['avgTone_msgsFromUser'] = toneSum / len(msgs)
            rootJson['toneTracking_msgsFromUser'] = toneTracking[:5]
        return rootJson

    def getRelationship(userScore, contactScore):
        return (userScore + contactScore) / 2 

    def extractToneAverage(self, tone):
        """ Tone is the JSON from Watson Tone Analyzer """
        toneSum = 0
        toneStyles = tone['children']
        for style in toneStyles:
            if style['id'] == 'emotion_tone':
                styleTypeInfo = style['id']['children']
                for sInfo in styleTypeInfo:
                    if sInfo['id'] == 'Cheefulness':
                        toneSum = toneSum + sInfo['normalized_value']
                    if sInfo['id'] == 'Negative':
                        toneSum = toneSum - sInfo['normalized_value']
                    if sInfo['id'] == 'Anger':
                        toneSum = toneSum - sInfo['normalized_value']
        return toneSum / 3






