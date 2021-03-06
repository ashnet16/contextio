from pymongo import MongoClient
from pymongo.collection import ReturnDocument
from helpers.parser import Parser
import json
from nouslog import log

logger = log()

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017
DBS_NAME = 'nous'

class DataStore:

    def __init__(self):
        self.client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        self.db = self.client[DBS_NAME]
        self.parser = Parser()

    def getUser(self, id):
        users = self.db.users
        user = users.find_one({'_id': id })
        return user

    def getUserByContextId(self, context_id):
        users = self.db.users
        user = users.find_one({'context_id': context_id })
        return user

    def createUser(self, **user):
        users = self.db.users
        # Check if the user exists
        existingUser = self.getUser(user['_id'])
        print existingUser
        if existingUser != None:
            return existingUser
        user_id = users.insert_one(user).inserted_id
        return user

    def updateUser(self, id, **user):
        users = self.db.users
        result = users.update_one({ '_id': id }, { '$set': user })
        return result == 1

    def addUserSource(self, context_id, source):
        users = self.db.users
        result = users.update_one({ 'context_id': context_id }, { '$push': { 'sources': source } })
        return result == 1

    def addUserContact(self, id, **contact):
        users = self.db.users
        result = users.update_one({ '_id': id }, { '$push': { 'contacts': contact } })
        return result == 1

    def removeUserContact(self, id, **contact):
        users = self.db.users
        result = users.update_one({ '_id': id }, { '$pull': { 'contacts': contact } }).modified_count
        return result == 1

    def deleteContactData(self, id, **contact):
        messagesCollection = self.db.messages
        messagesCollection.remove({ 'from': id, 'to': { '$in': contact['emails'] }, 'owner': id })
        messagesCollection.remove({ 'to': id, 'from': { '$in': contact['emails'] }, 'owner': id })
        relationshipsCollection = self.db.relationships
        relationshipsCollection.remove({ '_id': contact['emails'][0] + '-->' + id, 'owner': id })
        print id + '-->' + contact['emails'][0]
        relationshipsCollection.remove({ '_id': id + '-->' + contact['emails'][0], 'owner': id })


    def saveMessages(self, messages):
        messagesCollection = self.db.messages
        counter = 0
        for message in messages:
            result = messagesCollection.update({'_id': message['_id']}, message, True)
            ++counter
        return counter == len(messages)

    def saveMessage(self, **message):
        messagesCollection = self.db.messages
        result = messagesCollection.update({'_id': message['_id']}, message, True)
        return message

    def savePersonality(self, **personality):
        personalityCollection = self.db.personality
        result = personalityCollection.update({ '_id': personality['_id']}, personality, True)
        return personality

    def savePersonalities(self, *personalities):
        personalityCollection = self.db.personality
        result = personalityCollection.insert_many(personalities)
        return len(result.inserted_ids) == len(personalities)

    def hasPersonality(self, email):
        personalityCollection = self.db.personality
        num = personalityCollection.find( {'user': email}).count()
        if num > 0:
            return True
        else:
            return False

    def getFullBig5(self, email):
        print email
        personalityJson = {}
        personalityCollection = self.db.personality
        personalityData = personalityCollection.find_one({'_id':email},{'personality':1})
        if(personalityData):
            return self.parser.parseFullBig5(personalityData)
        else:
            return None

    def getMessagesFromUser(self, email):
        msgJson = {}
        messagesCollection = self.db.messages
        messages = messagesCollection.find({'from':email})
        mList = []
        for m in messages:
            newMsg = m
            newMsg['tone'] = self.parser.parseTone(newMsg)
            mList.append(newMsg)
        msgJson[email] = mList
        return msgJson

    def getContactToneBySender(self, email):
        messagesCollection = self.db.messages
        messages = messagesCollection.find({'from':email})
        result = []
        for message in messages:
            msg = {
                "from": message['from'],
                "datetime": message['datetime'],
                "to": message['to'],
                "owner": message['owner'],
                "_id": message['_id'],
                "subject": message['subject'],
                "tone": {}
            }
            for tone in message['tone']['children']:
                for child in tone['children']:
                    msg['tone'][tone['name'] + '.' + child['name']] = child['normalized_score']
            result.append(msg)
        return result

    def getContactToneBySenderAndReceiver(self, sender, receiver):
        messagesCollection = self.db.messages
        messages = messagesCollection.find({'from':sender, 'to': receiver})
        result = []
        for message in messages:
            msg = {
                "from": message['from'],
                "datetime": message['datetime'],
                "to": message['to'],
                "owner": message['owner'],
                "_id": message['_id'],
                "subject": message['subject'],
                "tone": {}
            }
            for tone in message['tone']['children']:
                for child in tone['children']:
                    msg['tone'][tone['name'] + '.' + child['name']] = child['normalized_score']
            result.append(msg)
        return result

    def addContact(self, contactId, **contact):
        contactsCollection = self.db.contacts
        newContact = contactsCollection.update( {'_id': contactId}, {"$set": contact}, upsert = True)
        return newContact

    def updateContactStatus(self, contactId, status):
        contactsCollection = self.db.contacts
        newContact = contactsCollection.find_one_and_update( {'_id': contactId}, {'$set': { 'is_selected': status }}, return_document=ReturnDocument.AFTER )
        print 'find and update ', newContact
        return newContact

    def getContactsByUser(self,  userEmail, selected=None):
        contactsCollection = self.db.contacts
        print 'getContactsByUser ',  userEmail
        if selected is None:
            # get all contacts
            return contactsCollection.find( {'user': userEmail} )
        elif selected is True:
            return contactsCollection.find( {'user': userEmail, 'is_selected': True} )
        elif selected is False:
            return contactsCollection.find( {'user': userEmail, 'is_selected': False} )

    def hasContactsPopulated(self, userEmail):
        contactsCollection = self.db.contacts
        return contactsCollection.find( {'user': userEmail}).count()

    def getRelationshipsForUser(self, userEmail):
        relationshipsCollection = self.db.relationships
        return list(relationshipsCollection.find({'hostemail':userEmail}))

    def saveRelationshipInfo(self, owner, userFirstName, userEmail, contactInfo):
        relationshipsCollection = self.db.relationships
        messagesCollection = self.db.messages

        msgsForTone  = messagesCollection.find({'from':contactInfo['email'], 'to': userEmail}).sort('datetime', 1)
        mList = []
        for m in msgsForTone:
            if 'avgTone' in m:
                mList.append(m['avgTone'])

        limitedMessages = list(messagesCollection.aggregate([
                     { '$match': {'from':contactInfo['email'], 'to': userEmail} },
                     { '$sort': { 'datetime': -1 } },
                     { '$limit': 10 },
                     { '$group': { '_id': "$email", 'avg': { '$avg': "$avgTone" } } }
                   ]))

        normLen = len(mList)
        if normLen > 5:
            mList = mList[-5:]
        else:
            mList = mList[0:normLen]

        if('tree' in contactInfo['personality']):
            personality = self.parser.flattenBig5(contactInfo['personality'])
        else:
            personality = {
                'Openness': 0,
                'Conscientiousness': 0,
                'Extraversion': 0,
                'Agreeableness': 0,
                'Emotional range': 0,
                'relationshipScore': 0
            }
        avgTone = limitedMessages[0]['avg'] if len(limitedMessages) > 0 else 0
        contactsToInsert = {}
        contactsToInsert['_id'] = contactInfo['email'] + '-->' + userEmail
        contactsToInsert['recipientmail'] = contactInfo['email']
        contactsToInsert['hostfirstname'] = userFirstName
        contactsToInsert['hostemail'] = userEmail
        contactsToInsert['Average tone'] = avgTone
        contactsToInsert['contactInfo'] = contactInfo['email']
        contactsToInsert['relationshipScore'] = contactInfo['relationshipScore']
        contactsToInsert['openness'] = personality['Openness']
        contactsToInsert['conscientiousness'] = personality['Conscientiousness']
        contactsToInsert['extraversion'] = personality['Extraversion']
        contactsToInsert['agreableness'] = personality['Agreeableness']
        contactsToInsert['emotional range'] = personality['Emotional range']
        contactsToInsert['owner'] = owner

        ctr = 0
        for t in mList:
            tName = 'tone' + str(ctr)
            contactsToInsert[str(tName)] = t
            ctr = ctr + 1

        print 'saving relationship' + contactInfo['email'] + '-->' + userEmail
        result = relationshipsCollection.update({ '_id': contactsToInsert['_id'] }, contactsToInsert, True)
        if result['ok'] == 1:
            return True
        else:
            logger.info("Did not insert contact %s ", contactInfo['email'])

    def delete_account(self, context_id):
        """ This function grabs the list of collections in the nous database and removes any document related to the context_id. In addition, it deletes the user account from contextio"""
        try:
            collections = [collection for collection in  self.db.collection_names() if not collection.startswith('system.')]
            for collect in collections:
               self.db[collect].remove({'context_id':context_id})
               return True
            logger.info('{0} data removed from all collections'.format(context_id))
        except Exception as e:
            logger.error('Encountered the following error when trying to delete account {0}:{1}'.format(context_id, e))
            return False

    def getmailboxcount(self, context_id):
        """ This function locates all documents within all collections in the nous database and deletes the documents as one part of the account deletion process."""
        document = self.db.users.find({"context_id":context_id})
        #print "document ", document
        mailbox_count = [x for x in document]
        if len(mailbox_count) > 0:
            if 'mailboxes' in mailbox_count[0]:
                return mailbox_count[0]['mailboxes']

    def updatemailbox(self, context_id, mailboxes):
        try:
            self.db.users.update({"context_id" : context_id},{ '$set': { "mailboxes" : mailboxes}})
            logger.info('Mailbox was added or deleted')
        except Exception as e:
            logger.error('The following issue was encountered when trying to update mailboxes:{0}'.format(context_id))








    #def getMessages(self, email):
