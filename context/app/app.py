import os
import json

#Routings go here

from flask import Flask, render_template, request, url_for, make_response, session, redirect
from authomatic import Authomatic
from authomatic.adapters import WerkzeugAdapter
from config import CONFIG
import multiprocessing
import logging

import contextio as c
from data.datastore import DataStore
from helpers.parser import Parser

from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService

from passlib.hash import pbkdf2_sha256

dataStore = DataStore()


# Adding logging
logger = logging.getLogger('Nous')
logger.setLevel(logging.INFO)
nouslog = logging.FileHandler(os.path.join(os.path.abspath(('logs/nous.log'))),'a')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
nouslog.setFormatter(formatter)
logger.addHandler(nouslog)

logger.info('TEST')

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

def runAnalysis(userEmail):
    user = dataStore.getUser(userEmail)
    params = {
        'id': user["context_id"]
    }
    account = c.Account(context_io, params)
    # variables below are just for debugging
    mList = []
    tList = []
    totalUserMsgs = []
    #cList = []
    # Put it to 10 contacts to be displayed as the limit for now
    numOfContacts = 1
    contacts = user['contacts']
    contactRootJsonList = []
    for contact in contacts:
        logger.info("contact %s", contact)
        contactAvgTone = 0
        singleUserAvgTone = 0
        try:
            # we need to get user<->contact messages first
            userMsgs = account.get_messages(sender = userEmail, to=contact['emails'][0], limit=2, include_body=1, body_type="text/plain")
            contactMsgs = account.get_messages(sender = contact['emails'][0], limit=2, include_body=1, body_type="text/plain")
        except:
            errMsg = sys.exc_info()[0]
            session.clear()
            return render_template ('error.html', errMsg = errMsg)
        if len(contactMsgs) > 0:
            contactRootJson = parser.analyzeMessages(contactMsgs, **{'type_': 'contact', 'from_': contact['emails'][0], 'to': userEmail, 'personality':True})
            contactRootJsonList.append(contactRootJson)
            contactAvgTone = contactRootJson['avgTone_msgsFromContact']
        if len(userMsgs) > 0:
            userRootJson = parser.analyzeMessages(userMsgs, **{'type_': 'singleUser', 'from_': contact['emails'][0], 'to':userEmail, 'personality':False})
            totalUserMsgs = userMsgs + totalUserMsgs
            singleUserAvgTone = userRootJson['avgTone_msgsFromUser']
        if contactAvgTone != 0 and singleUserAvgTone != 0:
            userRootJson['relationshipScore'] = parser.getRelationship(contactAvgTone, singleUserAvgTone)
    userRootJson = parser.analyzeMessages(totalUserMsgs, **{'type_': 'masterUser', 'from_':userEmail, 'personality': True,'tone': True})
    userRootJson['contacts'] = contactRootJsonList
    dataStore.updateUser(userEmail, **{ 'pending_analysis': False })
    print '*********Completed initial analysis********'
    return userRootJson

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
                'sources': [result.user.email],
                'contacts': [],
                'pending_sync': True
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
            session.clear()
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
    user = dataStore.getUser(userEmail)
    params = {
        'id': user["context_id"]
    }
    account = c.Account(context_io, params)
    try:
        getContacts(account.get_contacts(limit = 1))
    except:
        session.clear()
        return render_template('error.html', errorMsg="Error Retrieving Contacts")
    if(user['pending_sync']):
        return render_template('inbox.html', contactList=[], jsonOut = json.dumps({}), user=user)
    elif(user['pending_contacts']):
        return render_template('inbox.html', contactList=session['contacts'], jsonOut = json.dumps({}), user=user)
    elif(user['pending_analysis']):
        return render_template('inbox.html', contactList=session['contacts'], jsonOut = json.dumps({}), user=user)
    else:
        # get analysis data from mongodb and display the inbox
        return render_template('inbox.html', contactList=user['contacts'], jsonOut = json.dumps({}), user=user)

@app.route('/do-analysis', methods=['POST'])
def doAnalysis2():
    dataStore.updateUser(session["email"], **{ 'pending_analysis': True, 'pending_contacts': False })
    p = multiprocessing.Process(target=runAnalysis, args=(session['email'],))
    p.start()
    return json.dumps({ 'message': 'Running analysis'})

def getContacts(contacts):
    contactList = []
    for contact in contacts:
        contactList.append(contact.email)
    session['contacts'] = contactList

def createContextAccount(**args):
    # check if the account exists
    accounts = context_io.get_accounts(**{ 'email': args['email']})
    if len(accounts) > 0:
        return accounts[0].id

    accountData = {
        'email': args['email'],
        'first_name': args['first_name']
    }
    print accountData
    discoveryObject = getServerSettings(context_io, args['email']);
    account = context_io.post_account(**accountData)
    sourceAdded = updateServerSettings(
        accountObject=account,
        email=args['email'],
        provider_refresh_token=args['refresh_token'],
        provider_consumer_key=CONFIG['google']['consumer_key'],
        discoveryObject=discoveryObject)
    #account.post_sync()
    dataStore.updateUser(args['email'], **{'context_id': account.id})
    return account.id

@app.route('/mailbox-sync-callback', methods=['POST'])
def mailboxSyncCallback():
    accountId = request.json['account_id']
    user = dataStore.getUserByContextId(accountId)
    dataStore.updateUser(user['_id'], **{ 'pending_contacts': True, 'pending_sync': False })
    return 'OK'
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

@app.route('/add-mailbox', methods=["POST"])
def addMailbox():
    if request.method == 'POST':
        email = request.json["email"]
        account = c.Account(context_io, { 'id': session["context_id"] })
        result = account.post_connect_token(**{
        "callback_url": url_for('mailboxCallback', _external=True),
        "email": email,
        "first_name": session["firstname"]
        })
        return json.dumps(result);

@app.route('/remove-mailbox', methods=["POST"])
def removeMailbox():
    if request.method == 'POST':
        label = request.json["label"]
        account = c.Account(context_io, { 'id': session["context_id"] })
        source = c.Source(account, { 'label': label })
        return json.dumps(source .delete());

@app.route('/mailboxes', methods=["GET"])
def mailboxes():
    account = c.Account(context_io, { 'id': session["context_id"] })
    sources = account.get_sources();
    return render_template('mailboxes.html', sources=sources)


# for when user wants to see more contacts, see inbox.html, when press on arrow, grabs how many times arrows has been pressed with js
# and then displays contacts based on count * offset * 10
@app.route('/showMoreContacts')
def showMoreContacts():
    account = c.Account(context_io, { 'id': session["context_id"] })
    numOfContacts = 30
    contacts = account.get_contacts(limit=numOfContacts)
    contactList = []
    for contactObj in contacts:
        contactList.append(contactObj.email)
    return render_template('moreContacts.html', listOfContacts = contactList)

@app.route('/selectContact', methods=["POST"])
def selectContact():
    userAccount = c.Account(context_io, { 'id': session["context_id"] })
    contactEmail = request.json["email"]
    userSelectedContact = c.Contact(userAccount,{'email':contactEmail})
    userSelectedContact.get()
    user = dataStore.getUser(session['email'])
    dataStore.addUserContact(user['_id'],  ** { 'name': userSelectedContact.name, 'emails': [contactEmail] })
    return json.dumps({ 'message': 'Contact added' })

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
        "type": "IMAP",
        'callback_url': url_for('mailboxSyncCallback', _external=True)
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
        "type": "IMAP",
        'callback_url': url_for('mailboxSyncCallback', _external=True)
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
