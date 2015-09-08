from pymongo import MongoClient
from pymongo.collection import ReturnDocument 
import json
from datetime import datetime
import time
from dateutil import parser
from collections import defaultdict
import sys, os
from data.datastore import DataStore
from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))


toneAnalyzer = ToneAnalyzerService(os.getenv("VCAP_SERVICES"))
personalityAnalyzer = PersonalityInsightsService(os.getenv("VCAP_SERVICES"))

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017
DBS_NAME = 'enron'


class EnronDB:

    def __init__(self, email, firstname):
        self.client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        self.db = self.client[DBS_NAME]
     	self.dataStore = DataStore()
        self.firstname = firstname
        self.email = email
        self.contactList = []
        self.msgCounter = defaultdict(int)
        self.msgTracker = {}
        self.contacts = []
        self.user = {}
        self.messages = []
        self.personality = {}
        self.contactInfo = {}
        self.populateUser()
        self.populateMessagesFromUser()
        self.populateContacts()
        self.saveInfo()

    def populateUser(self):
    	self.user['_id'] = self.email
    	self.user['firstname'] = self.firstname
    	self.user['pending_contacts'] = False
    	self.user['pending_sync'] = False
    	self.user['pending_analysis'] = False
        self.user['context_id'] = self.email
        #print 'after populateUser ', self.user
    	return

    def getValidContacts(self, values):
    	contacts = values.split()
        msgContact = []
        for contact in contacts:
            c= contact.strip()
            if '@' in c:
                if c not in self.contactList:
                    self.contactList.append(c)
                msgContact.append(c)
        if len(msgContact) > 1000:
            return []
        #print ' == all validContacts ', len(self.contactList)
        #print ' == msgContact ', len(msgContact)
    	#if len(validContacts) > 5:
    	#	return []
    	#else:
        return msgContact



    def cleanContent(self, content):
        breaker1 = '-----Original Message-----'
        offset1 = content.find(breaker1)
        if offset1 >= 0:
            content = content[0:offset1]
        breaker2 = '---Forwarded by'
        offset2 = content.find(breaker2)
        if offset2 >= 0:
            content = content[0:offset2]
        return content


    def populateMessagesFromUser(self):
    	""" Returns a list of messages, driver function
    	"""
        messages = self.db.messages
        messagesFrom = messages.find({'headers.From':self.email}).sort([('headers.Date', -1)]).limit(1000)  
        print '==== TOTAL MESSAGES ====' , messagesFrom.count()  
        allContent = ''
        for message in messagesFrom:
        	#filter contacts
            contacts = []
            if 'To' not in message['headers']:
                continue
            msgContact = self.getValidContacts(message['headers']['To'])     
           
    		# duplicate message for each contact
            nousMessage = {}         
            nousMessage['from'] = self.email
            nousMessage['to'] = self.contactList
            nousMessage['subject'] = message['headers']['Subject']
            nousMessage['_id'] =  (str(message['_id']))[10:30]
            s = parser.parse(message['headers']['Date'])
            unixtime = time.mktime(s.timetuple())
            nousMessage['datetime'] = unixtime
            #get message content to pass to watson
            content = self.cleanContent(message['body'])
            #print 'content ', content 
            toneJson = toneAnalyzer.getTone(content.encode('utf-8'))
            nousMessage['tone'] = toneJson
            #print 'toneJson ', nousMessage['_id']
            self.messages.append(nousMessage)
            for contact in msgContact:
                if contact in self.msgTracker:
                    if self.msgTracker[contact] < nousMessage['datetime']:
                        self.msgTracker[contact] = nousMessage['datetime']
                self.msgCounter[contact] += 1
        	# allContent for personality
        	allContent = allContent + content
        print '== after populateMessagesFromUser ', len(self.messages)
        self.populatePersonality(self.email, allContent)
       	return

    def populateContacts(self):
        newContacts = []
        for key, value in sorted((self.msgCounter).iteritems(), key=lambda (k,v): (v,k)):
            newContacts.append(key)
        newContacts = newContacts[:30]
        #print 'newContacts ', newContacts
    	for contact in newContacts:
            c = {}
            cInfo = self.populateMessagesFromContact(contact)
            if cInfo['numMsgs'] == 0:
                continue
            c['_id'] = self.email + '_' + contact
            c['is_selected'] = True
            emails = []
            emails.append(contact)
            c['emails'] = emails
            c['email'] = contact
            c['user'] = self.email
            c['count'] =cInfo['numMsgs']
            c['last_received'] = cInfo['last_received']
            if contact in self.msgTracker:
    	       c['last_sent'] = self.msgTracker[contact]
            c['name'] = cInfo['name']
            self.contacts.append(c)
        #print ' == after populateContacts ', self.contacts
        self.user['contacts'] = self.contacts
    	return

    def populateMessagesFromContact(self, contact):
    	cInfo = {}
        messages = self.db.messages
    	messagesFrom = messages.find({'headers.From':contact, 'headers.To': self.email}).sort([('headers.Date', -1)]).limit(50)
    	cInfo['numMsgs'] = messagesFrom.count()
    	lastReceived = 0
        allContent = ''
        name = ''
        for message in messagesFrom:
            content = message['body']
            toneJson = toneAnalyzer.getTone(content.encode('utf-8'))
            nousMessage = {}
            nousMessage['tone'] = toneJson
            nousMessage['from'] = contact
            nousMessage['to'] = self.email
            nousMessage['subject'] = message['headers']['Subject'] 
            nousMessage['_id'] = (str(message['_id']))[10:30]
            s = parser.parse(message['headers']['Date'])
            unixtime = time.mktime(s.timetuple())
            nousMessage['datetime'] = unixtime
            if unixtime > lastReceived:
                lastReceived = unixtime
            self.messages.append(nousMessage)
            if len(name) == 0:
                name = message['headers']['X-From']
            allContent = allContent + content
        cInfo['last_received']  = lastReceived
        cInfo['name'] = name
        #print 'after populateMessagesFromContact ', len(self.messages)
        self.populatePersonality(contact, allContent)
        return cInfo

    def populatePersonality(self, email, allContent):
    	personality = personalityAnalyzer.getProfile(allContent.encode('utf-8'))
        if 'tree' in personality:
            self.dataStore.savePersonality(**{ '_id': email, 'personality': personality})
        #print 'allContent ', allContent
        #print 'after populatePersonality ', self.personality
        return

    def saveInfo(self):
    	self.dataStore.saveMessages(self.messages)
        #print 'user ', self.user
    	self.dataStore.saveUser(self.user)
    	for contact in self.contacts:
            #print 'contact ' , contact
            self.dataStore.saveContact(contact)
    	return

if __name__ == "__main__":
    print ' -- START KEN LAY --'
    EnronDB('kenneth.lay@enron.com', 'Ken Lay')
    print ' -- START JEFF SKILLING --'
    EnronDB('jeff.skilling@enron.com', 'Jeff Skilling')
    print ' -- START JEFFREY SHANKMAN --'
    EnronDB('jeffrey.shankman@enron.com', 'Jeffrey Shankman')
    print ' -- START VINCE KAMINSKY --'
    EnronDB('vince.kaminski@enron.com', 'Vince Kaminsky')
    print ' -- START BENJAMIN ROGERS --'
    EnronDB('benjamin.rogers@enron.com', 'Benjamin Rogers')
    print ' -- START GERALD NEMEC --'
    EnronDB('gerald.nemec@enron.com', 'Gerald Nemec')
    print ' -- START DAREN FARMER --'
    EnronDB('daren.farmer@enron.com', 'Daren Farmer')
    print ' -- START DAREN FARMER --'
    EnronDB('jeff.skilling@enron.com', 'Jeff Skilling')


