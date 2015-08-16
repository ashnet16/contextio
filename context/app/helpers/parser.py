import json
import re
import os
import logging

from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService

# Adding logging
logger = logging.getLogger('Nous')
logger.setLevel(logging.INFO)
nouslog = logging.FileHandler(os.path.join(os.path.abspath(('logs/nous.log'))),'a')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
nouslog.setFormatter(formatter)
logger.addHandler(nouslog)



logger.info('In Parser')
 
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

    def byteify(input):
        if isinstance(input, dict):
            return {byteify(key):byteify(value) for key,value in input.iteritems()}
        elif isinstance(input, list):
            return [byteify(element) for element in input]
        elif isinstance(input, unicode):
            return input.encode('utf-8')
        else:
            return input


    def getBig5(self, personality):
        self.personality = []
        level1 = personality['tree']
        level2 = level1['children']
        level3 = level2[0]['children']
        level4 = level3[0]
        level5 = level4['children']
        self.personality = {}
        for child in level5:
            name = child['name']
            self.personality[str(name)] = child['percentage']
        return
           

    def analyzeMessages(self, msgs, **params):
        rootJson = {}
        rootJson['email'] = params['from_']
        logger.info('FROM %s', rootJson['email'])
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
            message = {}
            message['datetime'] = m.date 
            message['subject'] = m.subject
            if params['type_'] != 'masterUser':
                message['to'] = params['to']
            message['from'] = params['from_'] 
            logger.info('msg %s', m.body)
            for mInfo in m.body:
                content = self.extractMessage(mInfo['content'])
                message['content'] = content
                logger.info('content %s', content)
                msgContentList.append(content)
                toneJson = self.toneAnalyzer.getTone(content.encode('utf-8'))
                logger.info('tone %s', toneJson)
                message['tone'] = toneJson
                toneAve = self.extractToneAverage(toneJson)
                toneTracking.append(toneAve)
                toneSum = toneSum + toneAve

                # to do get average message
                # aggregate message content
                allContent = allContent + content
            emailMessages.append(message)
        if params['personality'] == True:
            allContent = allContent.encode('utf-8')
            personalityJson = self.personalityAnalyzer.getProfile(allContent)
            if 'error' in personalityJson or u'error' in personalityJson:
                rootJson['personality'] = {}
            else:
                self.getBig5(personalityJson)
                rootJson['personality'] = self.personality
        if params['type_'] == 'masterUser':
            rootJson['emailMessages'] = emailMessages
        if isContact:
            rootJson['avgTone_msgsFromContact'] = toneSum / len(msgs)
            rootJson['toneTracking_msgsFromContact'] = toneTracking[:5]
        else:
            if len(msgs) > 0:
                rootJson['avgTone_msgsFromUser'] = toneSum / len(msgs)
            else:
                rootJson['avgTone_msgsFromUser'] = 0
            rootJson['toneTracking_msgsFromUser'] = toneTracking[:5]
        return rootJson

    def getRelationship(self, userScore, contactScore):
        return (userScore + contactScore) / 2 

    def extractToneAverage(self, tone):
        """ Tone is the JSON from Watson Tone Analyzer """
        toneSum = 0
        toneStyles = tone['children']
        for style in toneStyles:
            if style['id'] == 'emotion_tone':
                styleTypeInfo = style['children']
                for sInfo in styleTypeInfo:
                    if sInfo['name'] == 'Cheefulness':
                        toneSum = toneSum + float(sInfo['raw_score'])
                    if sInfo['name'] == 'Negative':
                        toneSum = toneSum - float(sInfo['raw_score'])
                    if sInfo['name'] == 'Anger':
                        toneSum = toneSum - float(sInfo['raw_score'])
        return toneSum / 3






