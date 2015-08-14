import json
import re
 
class Parser:
    """Takes in Message JSON object from API and returns requested attributes"""

    def __init__(self):
        # NB This was only tested in GMAIL, we don't know if the thread msg header format is uniform
        # NB Have to extend pattern to include support for foreign language
        #threadHeaderRegExp = re.compile(r'On\s(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s[A-Z]?[a-z]{2,3}\s[0-9]{1,2},\s[0-9]{4}\sat\s[0-9]{1,2}:[0-9]{2}\s(?:AM|PM),\s[^<]+<[^@]+@[^>]+>\swrote:')
        self.threadHeaderRegExp = re.compile(r'On\s(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s[A-Z]?[a-z]{2,3}\s[0-9]{1,2},\s[0-9]{4}\sat\s[0-9]{1,2}:[0-9]{2}\s(?:AM|PM),\s[^<]+<[^@]+@[^>]+>\swrote:')                    
        
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