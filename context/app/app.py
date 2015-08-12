import os
import json

#Routings go here

from flask import Flask, render_template, request, url_for
import contextio as c
from data.datastore import DataStore
dataStore = DataStore()
#from pymongo import Connection
#import json
#from bson import json_util
#from bson.json_util import dumps

app = Flask(__name__)

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017
DBS_NAME = 'nous'
#COLLECTION_NAME = 'projects'
#FIELDS = {'school_state': True, 'resource_type': True, 'poverty_level': True, 'date_posted': True, 'total_donations': True, '_id': False}


# contextio key and secret key
#CONSUMER_KEY = 'l57sr7jp'
#CONSUMER_SECRET = 'm0mRv5iaojsNWnvu'

context_io = c.ContextIO(
   consumer_key=CONSUMER_KEY,
   consumer_secret=CONSUMER_SECRET)

@app.route('/')
def index():
        return render_template('userLogin.html')

# sends user info to be our contextio account so that we can later on see their email
@app.route('/sendUserInfo', methods=['POST'])
def sendUserInfo():
    firstName = request.json["firstName"]
    email = request.json["email"]
    password = request.json["password"]

    # Check if the user exists
    user = dataStore.getUser(email)
    if user != None:
        raise Exception('Account exists with the provided email')

    user_id = dataStore.createUser(**{
        '_id': email,
        'firstname': firstName,
        'sources': [email]
    });
    discoveryObject = getServerSettings(context_io, email);
    print discoveryObject.found
    accountData = {
        "email": email,
        "first_name": firstName
    }
    account = context_io.post_account(**accountData)
    sourceAdded = updateServerSettings(
        accountObject=account,
        email=email,
        password=password,
        discoveryObject=discoveryObject)
    account.post_sync()
    dataStore.updateUser(user_id, **{'context_id': account.id})
    return account.id

def getServerSettings(contextioObject,email):
	source = "IMAP" # contextio only supports IMAP email servers
	IMAPSettings = {"source_type":source,"email":email}
	settingForEmail = contextioObject.get_discovery(**IMAPSettings)
	return settingForEmail

def updateServerSettings(accountObject, email, password, discoveryObject):
    serverSettingIsUpdated = True
    sourceData = {
        "email": email,
        "server": discoveryObject.imap["server"],
        "username": discoveryObject.imap["username"],
        "password": password,
        "use_ssl": 1,
        "port": discoveryObject.imap["port"],
        "type": "IMAP"
    }
    print sourceData
    itIsSuccessful = accountObject.post_source(**sourceData)
    if itIsSuccessful != False:
    	serverSettingIsUpdated = False
    return serverSettingIsUpdated

#@app.route("/donorschoose/projects")
#def donorschoose_projects():
   # connection = Connection(MONGODB_HOST, MONGODB_PORT)
   # collection = connection[DBS_NAME][COLLECTION_NAME]
   #projects = collection.find(fields=FIELDS)
   # json_projects = []
   # for project in projects:
       # json_projects.append(project)
   # json_projects = json.dumps(json_projects, default=json_util.default)
   # connection.disconnect()
   #return json_projects

from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService

# Create the Personality Insights Wrapper
personalityInsights = PersonalityInsightsService(os.getenv("VCAP_SERVICES"))
toneAnalyzer = ToneAnalyzerService(os.getenv("VCAP_SERVICES"))

@app.route('/tone', methods=['POST'])
def tone():
    data = request.form['text'];
    toneJson = toneAnalyzer.getTone(data.encode('utf-8'))
    return json.dumps(toneJson)

@app.route('/synonym', methods=['POST'])
def synonym():
    words = request.form['words'];
    limit = request.form['limit'];
    toneJson = toneAnalyzer.getSynonym(words, limit)
    return json.dumps(toneJson)

if __name__ == "__main__":
    app.run(host='127.0.0.1',port=5000,debug=True)
