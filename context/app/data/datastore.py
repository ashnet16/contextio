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
        user = users.find_one({'id': id })
        return user

    def createUser(self, **user):
        users = self.db.users
        user_id = users.insert_one(user).inserted_id
        return user_id

    def updateUser(self, id, **user):
        users = self.db.users
        result = users.update_one({ '_id': id }, { '$set': user })
        return result == 1
