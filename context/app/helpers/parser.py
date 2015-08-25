import json
import re
import os

from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService
from nouslog import log

logger = log()



logger.info('In Parser')

class Parser:
    """Takes in  JSON object from API and returns requested attributes"""

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

    def flattenBig5(self, personality):
        flatPersonality = {}
        level1 = personality['tree']
        level2 = level1['children']
        level3 = level2[0]['children']
        level4 = level3[0]
        level5 = level4['children']
        for child in level5:
            name = child['name']
            flatPersonality[str(name)] = child['percentage']
        return flatPersonality

    def parseFullBig5(self, personalityData):
        fullBig5 = []
        personality = personalityData['personality']
        level1 = personality['tree']
        level2 = level1['children']
        level3 = level2[0]['children']
        level4 = level3[0]
        level5 = level4['children']
        for child in level5:
            oneBig5 = {}
            oneBig5['name'] = child['name']
            oneBig5['percentage'] = child['percentage']
            subFacet = child['children']
            subFacets = []
            for s in subFacet:
                subFacet = {}
                subFacet['name'] = s['name']
                subFacet['percentage'] = s['percentage']
                subFacets.append(subFacet)
            oneBig5['children'] = subFacets
            fullBig5.append(oneBig5)
        return fullBig5

    def analyzeMessages(self, msgs, **params):
        """ If the messages are sent by the contact:
            This function populates in senderJson to be sent to datastore,
                message collection - messages sent by contact, get tone and tone avg
                contact collection - big5 personality, num of emails
                contact message avg tone
            If messages are sent by the user:
            This function computes the personality, and values in the returned json are
            use to compute average tone and relationship score
            Return: senderJson
        """
        senderJson = {}
        senderJson['email'] = params['from_']
        senderJson['numberOfEmails'] = len(msgs)
        self.output = {}
        message = {}
        emailMessages = []
        allContent = '\n'
        toneSum = 0
        totalAvg = 0
        for m in msgs:
            message = {}
            message['datetime'] =  m.date
            message['subject'] = m.subject
            message['from'] = params['from_']
            message['_id'] = m.message_id
            message['owner'] = params['owner']
            message['to'] =params['to']
            logger.info('msg %s', m.body)
            for mInfo in m.body:
                content = self.extractMessage(mInfo['content'])
                # message['content'] = content
                #logger.info('content %s', content)
                toneJson = self.toneAnalyzer.getTone(content.encode('utf-8'))
                logger.info('tone %s', toneJson)
                message['tone'] = toneJson
                toneAvg = self.extractToneAverage(toneJson)
                message['avgTone'] = toneAvg
                totalAvg = totalAvg + toneAvg
                # aggregate message content
                allContent = allContent + content
            emailMessages.append(message)

        # Get personality Big5 of contact based on all the messages she sent
        allContent = allContent.encode('utf-8')
        personalityJson = self.personalityAnalyzer.getProfile(allContent)
        if 'error' in personalityJson or u'error' in personalityJson:
            senderJson['personality'] = {}
        else:
            self.getBig5(personalityJson)
            senderJson['personality'] = personalityJson

        senderJson['emailMessages'] = emailMessages
        senderJson['avgTone'] = senderJson['numberOfEmails']
        return senderJson

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

    def parseTone(self, msg):
        toneJson = {}
        tone = msg['tone']
        level1 = tone['children']
        for toneType in level1:
            toneType['name']
            level2 = toneType['children']
            subElement = {}
            for typeElements in level2:
                subElement[(typeElements['name'])] = typeElements['normalized_score']
                #subElements.append(subElement)
            toneJson[(toneType['name'])] = subElement
        return toneJson

    def parseFullPersonality(self, personality):
        fullPersonalityJson = {}
        pTree = personality['personality']['tree']
        for p in pTree:
            pChild = p['child']
