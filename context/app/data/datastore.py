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

    def saveMessages(self, *messages):
        messagesCollection = self.db.messages
        result = messagesCollection.insert_many(messages)
        return len(result.inserted_ids) == len(messages)

    def saveMessage(self, **message):
        messagesCollection = self.db.messages
        result = messagesCollection.insert_one(message).inserted_id
        return message
