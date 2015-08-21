from pymongo import MongoClient
from helpers.parser import Parser
import json

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

    def addUserContact(self, id, **contact):
        users = self.db.users
        result = users.update_one({ '_id': id }, { '$push': { 'contacts': contact } })
        return result == 1

    def saveMessages(self, messages):
        messagesCollection = self.db.messages
        counter = 0
        for message in messages:
            result = messagesCollection.update({'_id': message['_id']}, message, True)
            ++counter
        return counter == len(messages)

    def saveMessage(self, **message):
        messagesCollection = self.db.messages
        result = messagesCollection.insert_one(message).inserted_id
        return message

    def savePersonality(self, **personality):
        personalityCollection = self.db.personality
        result = personalityCollection.update({ '_id': personality['_id']}, personality, True)
        return personality

    def savePersonalities(self, *personalities):
        personalityCollection = self.db.personality
        result = messagesCollection.insert_many(personalities)
        return len(result.inserted_ids) == len(personalities)

    def getFullBig5(self, email):
        print email
        personalityJson = {}
        personalityCollection = self.db.personality
        personalityData = personalityCollection.find({'_id':email},{'personality':1})
        if(personalityData[0]):
            return self.parser.parseFullBig5(personalityData[0])
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

    def getRelationshipsForUser(self, userEmail):
        relationshipsCollection = self.db.relationships
        return list(relationshipsCollection.find({'hostemail':userEmail}))

    def saveContactInfo(self, userFirstName, userEmail, contactInfo):
        relationshipsCollection = self.db.relationships
        messagesCollection = self.db.messages

        msgsForTone  = messagesCollection.find({'from':contactInfo['email'], 'to': userEmail}).sort('datetime', 1)
        mList = []
        for m in msgsForTone:
            mList.append(m['avgTone'])
        print mList

        limitedMessages = list(messagesCollection.aggregate([
                     { '$match': {'from':contactInfo['email'], 'to': userEmail} },
                     { '$sort': { 'datetime': -1 } },
                     { '$limit': 10 },
                     { '$group': { '_id': "$email", 'avg': { '$avg': "$avgTone" } } }
                   ]))

        for m in limitedMessages:
            print m['avg']

        normLen = len(mList)
        if normLen > 5:
            mList = mList[-5:]
        else:
            mList = mList[0:normLen]


        print 'tonelist ', mList

        personality = self.parser.flattenBig5(contactInfo['personality'])

        print 'personality ', personality

        contactsToInsert = {}
        contactsToInsert['_id'] = contactInfo['email'] + '-->' + userEmail
        contactsToInsert['recipientmail'] = contactInfo['email']
        contactsToInsert['hostfirstname'] = userFirstName
        contactsToInsert['hostemail'] = userEmail
        contactsToInsert['Average tone'] = limitedMessages[0]['avg']
        contactsToInsert['contactInfo'] = contactInfo['email']
        contactsToInsert['relationshipScore'] = contactInfo['relationshipScore']
        contactsToInsert['openness'] = personality['Openness']
        contactsToInsert['conscientiousness'] = personality['Conscientiousness']
        contactsToInsert['extraversion'] = personality['Extraversion']
        contactsToInsert['agreableness'] = personality['Agreeableness']
        contactsToInsert['emotional range'] = personality['Emotional range']

        ctr = 0
        for t in mList:
            tName = 'tone' + str(ctr)
            contactsToInsert[str(tName)] = t
            ctr = ctr + 1

        result = relationshipsCollection.update({ '_id': contactsToInsert['_id'] }, contactsToInsert, True)
        print result
        if result['nModified'] > 0:
            return True
        else:
            logger.info("Did not insert contact %s ", contactInfo['email'])

    #def getMessages(self, email):
