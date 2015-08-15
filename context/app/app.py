import os
import json

#Routings go here

from flask import Flask, render_template, request, url_for, make_response, session, redirect
from authomatic import Authomatic
from authomatic.adapters import WerkzeugAdapter
from config import CONFIG
import logging
from logging.handlers import RotatingFileHandler


import contextio as c
from data.datastore import DataStore
from helpers.parser import Parser

from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService

from passlib.hash import pbkdf2_sha256

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


# contextio key and secret key
CONSUMER_KEY = 'l57sr7jp'
CONSUMER_SECRET = 'm0mRv5iaojsNWnvu'

context_io = c.ContextIO(
   consumer_key=CONSUMER_KEY,
   consumer_secret=CONSUMER_SECRET)

authomatic = Authomatic(CONFIG, 'your secret string', report_errors=False)
parser = Parser()
toneAnalyzer = ToneAnalyzerService(os.getenv("VCAP_SERVICES"))

@app.route('/')
def index():
    if 'provider_name' in session:
        if session['provider_name'] == 'local':
            return render_template('inbox.html')
        else:
            if 'credentials' in session:
                credentials = authomatic.credentials(session["credentials"])
                if credentials.valid == True:
                    return redirect(url_for('inbox'))
    return render_template('userLogin.html')

@app.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login(provider_name):
    # check if their is a valid session already
    if 'provider_name' in session:
        if session['provider_name'] == 'local':
            return render_template('inbox.html')
        else:
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
            # Create a user. If the user already exists it simply return the user
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
    if 'provider_name' in session:
        if session['provider_name'] != 'local':
            if 'credentials' in session:
                credentials = authomatic.credentials(session["credentials"])
                if credentials.valid != True:
                    return render_template('index.html')
    userEmail = session["email"]
    params = {
        'id': session["context_id"]
    }
    account = c.Account(context_io, params)
    mList = []
    tList = []
    messageResults = account.get_messages(folder="\Sent", limit=2, include_body=1, body_type="text/plain")
    # Put it to 10 contacts to be displayed as the limit for now
    numOfContacts = 10
    contacts = account.get_contacts(limit = numOfContacts)
    print messageResults
    for mbody in messageResults:
        for m in mbody.get_body(type='text/plain'):
            data = parser.extractMessage(m['content'])
            toneJson = toneAnalyzer.getTone(data.encode('utf-8'))
            mList.append(data)
            tList.append(json.dumps(toneJson))
    #return render_template('inbox.html', messages=parser.retrieveAsText())
    return render_template('inbox.html', msgs=mList, tones=tList, contactList=contacts)

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
    # Check if the user exists
    user = dataStore.getUser(email);
    if user != None:
        # Compare password
        if pbkdf2_sha256.verify(password, user["password"]) == True:
            session["context_id"] = user["context_id"]
        else:
            raise Exception('Invalid account details!')
    else:
        user = dataStore.createUser(**{
            '_id': email,
            'firstname': firstName,
            'sources': [email],
            'password': pbkdf2_sha256.encrypt(password, rounds=200000, salt_size=16)
        });
        accountData = {
            'email': email,
            'first_name': firstName
        }
        account = context_io.post_account(**accountData)
        dataStore.updateUser(user['_id'], **{'context_id': account.id})
        session["context_id"] = account.id
    session["provider_name"] = 'local'
    session["email"] = user['_id']
    session['firstname'] = user['firstname'];
    return user['_id'];

@app.route('/mailboxcallback', methods=["GET"])
def mailboxCallback():
    print request.args.get('contextio_token')
    return redirect(url_for('inbox'))

@app.route('/add-mailbox', methods=["GET", "POST"])
def addMailbox():
    if request.method == 'POST':
        print url_for('mailboxCallback')
        email = request.json["email"]
        account = c.Account(context_io, { 'id': session["context_id"] })
        result = account.post_connect_token(**{
        "callback_url": url_for('mailboxCallback', _external=True),
        "email": email,
        "first_name": session["firstname"]
        })
        return json.dumps(result);
    else:
        return render_template('addMailbox.html')

# for when user wants to see more contacts, see inbox.html, when press on arrow, grabs how many times arrows has been pressed with js 
# and then displays contacts based on count * offset * 10
@app.route('/showMoreContacts')
def showMoreContacts():
    account = c.Account(context_io, { 'id': session["context_id"] })
    numOfContacts = 30
    contacts = account.get_contacts(limit=numOfContacts)
    return render_template('moreContacts.html', contactList = contacts)



def getServerSettings(contextioObject,email):
	source = "IMAP" # contextio only supports IMAP email servers
	IMAPSettings = {"source_type":source,"email":email}
	settingForEmail = contextioObject.get_discovery(**IMAPSettings)
	return settingForEmail

def updateServerSettingsWithPassword(accountObject, email, password, discoveryObject):
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


@app.route('/personality', methods=['POST'])
def personality():
    data = request.form['text'];
    personalityJson = personalityInsights.getProfile(data.encode('utf-8'))
    return json.dumps(personalityJson)

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
