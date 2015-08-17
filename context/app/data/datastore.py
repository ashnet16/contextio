from pymongo import MongoClient

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017
DBS_NAME = 'nous'

class DataStore:

    def __init__(self):
        self.client = MongoClient(MONGODB_HOST, MONGODB_PORT)
        self.db = self.client[DBS_NAME]

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
