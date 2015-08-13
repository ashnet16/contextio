import os
import json

#Routings go here

from flask import Flask, render_template, request, url_for, make_response, session, redirect
from authomatic import Authomatic
from authomatic.adapters import WerkzeugAdapter
from config import CONFIG
import contextio as c
from data.datastore import DataStore
dataStore = DataStore()
#from pymongo import Connection
#import json
#from bson import json_util
#from bson.json_util import dumps

app = Flask(__name__)
app.secret_key = 'nous session key'

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017
DBS_NAME = 'nous'
#COLLECTION_NAME = 'projects'
#FIELDS = {'school_state': True, 'resource_type': True, 'poverty_level': True, 'date_posted': True, 'total_donations': True, '_id': False}


# contextio key and secret key
CONSUMER_KEY = 'l57sr7jp'
CONSUMER_SECRET = 'm0mRv5iaojsNWnvu'

context_io = c.ContextIO(
   consumer_key=CONSUMER_KEY,
   consumer_secret=CONSUMER_SECRET)

authomatic = Authomatic(CONFIG, 'your secret string', report_errors=False)

@app.route('/')
def index():
    if 'credentials' in session:
        credentials = authomatic.credentials(session["credentials"])
        if credentials.valid == True:
            return redirect(url_for('inbox'))
    return render_template('userLogin.html')

@app.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login(provider_name):
    # check if their is a valid session already
    if 'credentials' in session:
        credentials = authomatic.credentials(session["credentials"])
        print credentials.valid
        if credentials.valid == True:
            return redirect(url_for('inbox'))
    # Create an OAuth2 request for the provider
    response = make_response()
    result = authomatic.login(
       WerkzeugAdapter(request, response),
       provider_name,
       session=session,
       session_saver=lambda: app.save_session(session, response)
    )
    # Assuming we got a result back process the response
    if result:
        if result.user:
            result.user.update()
            # Create a user. If the user already exists it simply return the _id
            user = dataStore.createUser(**{
                '_id': result.user.email,
                'firstname': result.user.first_name,
                'sources': [result.user.email]
            })

            session['firstname'] = result.user.first_name;
            session['email'] = result.user.email;

            session['provider_refresh_token'] = result.user.credentials.token
            session['provider_name'] = result.provider.name
            session['credentials'] = result.user.credentials.serialize()
            # check if the user already has a context_id
            if 'context_id' in user:
                session["context_id"] = user['context_id']
                return redirect(url_for('inbox'))
            else:
                session["context_id"] = createContextAccount(**{
                    'email': result.user.email,
                    'first_name': result.user.first_name,
                    'refresh_token': result.user.credentials.token
                })
                return redirect(url_for('inbox'))
        else:
            raise Exception('There was a problem getting your user info')
    else:
        return response

@app.route('/logout', methods=["GET"])
def logout():
    session.clear();
    return redirect(url_for('index'))

@app.route('/inbox', methods=['GET'])
def inbox():
    if 'credentials' in session:
        credentials = authomatic.credentials(session["credentials"])
        if credentials.valid == True:
            return render_template('inbox.html')
    return redirect(url_for('index'))

def createContextAccount(**args):
    # check if the account exists
    accounts = context_io.get_accounts(**{ 'email': args['email']})
    if len(accounts) > 0:
        return accounts[0].id

    accountData = {
        'email': args['email'],
        'first_name': args['first_name']
    }
    discoveryObject = getServerSettings(context_io, args['email']);
    account = context_io.post_account(**accountData)
    sourceAdded = updateServerSettings(
        accountObject=account,
        email=args['email'],
        provider_refresh_token=args['refresh_token'],
        provider_consumer_key=CONFIG['google']['consumer_key'],
        discoveryObject=discoveryObject)
    account.post_sync()
    dataStore.updateUser(args['email'], **{'context_id': account.id})
    return account.id

# sends user info to be our contextio account so that we can later on see their email
@app.route('/sendUserInfo', methods=['POST'])
def sendUserInfo():
    firstName = request.json["firstName"]
    email = request.json["email"]
    password = request.json["password"]

    user = dataStore.createUser(**{
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
    dataStore.updateUser(user['_id'], **{'context_id': account.id})
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

def updateServerSettings(accountObject, email, provider_refresh_token, provider_consumer_key, discoveryObject):
    serverSettingIsUpdated = True
    sourceData = {
        "email": email,
        "server": discoveryObject.imap["server"],
        "username": discoveryObject.imap["username"],
        "provider_refresh_token": provider_refresh_token,
        "provider_consumer_key": provider_consumer_key,
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
