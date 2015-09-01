import os
import json

#Routings go here

from flask import Flask, render_template, request, url_for, make_response, session, redirect
from authomatic import Authomatic
from authomatic.adapters import WerkzeugAdapter
from config import CONFIG
import multiprocessing

import contextio as c
from data.datastore import DataStore
from helpers.parser import Parser

from watson.personality import PersonalityInsightsService
from watson.tone import ToneAnalyzerService

# import itertools

toneAnalyzer = ToneAnalyzerService(os.getenv("VCAP_SERVICES"))
personalityAnalyzer = PersonalityInsightsService(os.getenv("VCAP_SERVICES"))

from passlib.hash import pbkdf2_sha256
dataStore = DataStore()

from nouslog import log
app = Flask(__name__)
app.secret_key = 'nous session key'

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017
DBS_NAME = 'nous'
# contextio key and secret key
CONSUMER_KEY = 'l57sr7jp'
CONSUMER_SECRET = 'm0mRv5iaojsNWnvu'


logger = log()

context_io = c.ContextIO(
   consumer_key=CONSUMER_KEY,
   consumer_secret=CONSUMER_SECRET)

authomatic = Authomatic(CONFIG, 'your secret string', report_errors=False)
parser = Parser()

def runAnalysis(userEmail):
    logger.info('runAnalysis %s ', userEmail)
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
    # contacts is the list of selected contacts in DB
    contacts = dataStore.getContactsByUser(userEmail, True)
    userFirstName = user['firstname']

    for contact in contacts:
        logger.info("contact in run analysis %s", contact)
        contactEmail = contact['email']
        try:
            # we need to get user<->contact messages first
            logger.info("getting email from %s ", contactEmail)

            userMsgs = account.get_messages(sender = userEmail, to=contactEmail, limit=20, include_body=1, body_type="text/plain")
            contactMsgs = account.get_messages(sender = contactEmail, limit=20, include_body=1, body_type="text/plain")
        except:
            errMsg = "Error Retrieving Contacts"
            session.clear()
            return render_template ('error.html', errorMsg = errMsg)

        print 'there are ' + str(len(userMsgs)) + ' messages from ' + userEmail + ' to ' + contactEmail + ' this contact'
        print 'there are ' + str(len(contactMsgs)) + ' messages to ' + userEmail + ' from ' + contactEmail + ' this contact'
        if len(contactMsgs) > 0:
            contactInfo = parser.analyzeMessages(contactMsgs, **{'from_': contactEmail, 'to': userEmail, 'owner': userEmail})
            dataStore.savePersonality(**{ '_id': contactInfo['email'], 'personality': contactInfo['personality']})
            dataStore.saveMessages(contactInfo['emailMessages'])
        else:
            contactInfo = {
                'numberOfEmails': len(contactMsgs),
                'emailMessages': [{}],
                'avgTone': 0,
                'email': contact['emails'][0],
                'personality': {}
            }

        if len(userMsgs) > 0:
            userInfo = parser.analyzeMessages(userMsgs, **{'from_': userEmail, 'to':contactEmail, 'owner': userEmail})
            dataStore.savePersonality(**{ '_id': userEmail, 'personality': userInfo['personality']})
            dataStore.saveMessages(userInfo['emailMessages'])
        else:
            userInfo = {
                'numberOfEmails': len(userMsgs),
                'emailMessages': [{}],
                'avgTone': 0,
                'email': userEmail,
                'personality': {}
            }

        if contactInfo['avgTone'] != 0 and userInfo['avgTone'] != 0:
            contactInfo['relationshipScore'] = parser.getRelationship(contactInfo['avgTone'], userInfo['avgTone'])
            userInfo['relationshipScore'] = parser.getRelationship(userInfo['avgTone'],contactInfo['avgTone'])
        else:
            contactInfo['relationshipScore'] = 0
            userInfo['relationshipScore'] = 0

        dataStore.saveRelationshipInfo(userEmail, userFirstName, userEmail, contactInfo)
        # Get the reversed relationship analysis. Do not have firstname on contact so using name
        dataStore.saveRelationshipInfo(userEmail, contact['name'], contactInfo['email'], userInfo)

    dataStore.updateUser(userEmail, **{ 'pending_contacts': False, 'pending_analysis': False })
    print '*********Completed initial analysis********'
    return

@app.route('/')
def index():
    if 'provider_name' in session:
        if session['provider_name'] == 'local':
        #return render_template('inbox.html')
            return redirect(url_for('inbox'))
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
                print 'lkj', credentials.valid
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
            #app_id = nous_id()
            user = dataStore.createUser(**{
                '_id': result.user.email,
                'firstname': result.user.first_name,
                'sources': [result.user.email],
                'contacts': [],
                'pending_sync': True,
                'pending_contacts': False,
                'pending_analysis': False,
                'mailboxes': 1

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
    mailboxcount = dataStore.getmailboxcount(session["context_id"])
    logger.info("Just checking" )
    if 'provider_name' in session:
        if session['provider_name'] != 'local':
            if 'credentials' in session:
                credentials = authomatic.credentials(session["credentials"])
                if credentials.valid != True:
                    return render_template('userLogin.html')
    userEmail = session["email"]
    user = dataStore.getUser(userEmail)
    try:
        #add error checking to avoid stale session variables
        sessionContextId = user["context_id"]
    except:
        session.clear()
        errMsg = "Expired Session"
        return render_template ('error.html', errorMsg = errMsg)
    params = {
        'id': sessionContextId
    }
    account = c.Account(context_io, params)
    # The following is a hack to get around limitation with callbacks to localhost
    if(user['pending_sync'] and 'localhost' in url_for('inbox', _external=True)):
        sources = account.get_sync()
        isOkay = False
        # The format of the response is awful so the following is as good as I could get
        for source in sources:
            if(sources[source] != None):
                for sync in sources[source]:
                    if(sources[source][sync]['initial_import_finished'] == True):
                        isOkay = True
        if(isOkay):
            dataStore.updateUser(user['_id'], **{ 'pending_sync': False, 'pending_contacts': True, 'pending_analysis': False })
            user['pending_contacts'] = True
            user['pending_sync'] = False
    # End of localhost hack

    #try:
    # getContacts(account.get_contacts(limit = 1))
    #logger.info("calling get contacts" )
    #except:
    #    session.clear()
    #    return render_template('error.html', errorMsg="Error Retrieving Contact On Account Creation")
    logger.info("pending sync %d", user['pending_sync'] )
    logger.info("pending contacts %d", user['pending_contacts'] )
    logger.info("pending analysis %d", user['pending_analysis'] )
    if(user['pending_sync']):
        return render_template('inbox.html', user=user)
    elif(user['pending_contacts']):
        return render_template('inbox.html', user=user)
    elif(user['pending_analysis']):
        logger.info("pending analysis contact" )
        return render_template('inbox.html', user=user)
    else:
        # get analysis data from mongodb and display the inbox
        return render_template('inbox.html', contactList=user['contacts'], user=user, mailboxcount = mailboxcount)

@app.route('/do-analysis', methods=['POST'])
def doAnalysis2():
    logger.info("in do analysis ")
    dataStore.updateUser(session["email"], **{ 'pending_analysis': True, 'pending_contacts': False })
    p = multiprocessing.Process(target=runAnalysis, args=(session['email'],))
    p.start()
    return json.dumps({ 'message': 'Running analysis'})

@app.route('/do-analysis-sync', methods=['POST'])
def doAnalysisSync():
    logger.info("in do analysis sync")
    dataStore.updateUser(session["email"], **{ 'pending_analysis': True, 'pending_contacts': False })
    jsonResult = runAnalysis(session['email'])
    return json.dumps(jsonResult)

#def getContacts(contacts):
#    logger.info('info from contextio %s', contacts)
#    contactList = []
#    for contact in contacts:
#        contactList.append(contact.email)
#        logger.info('in get contacts %s ', contact.email)
    #Lory: add to DB -- may be changed if we have the selected contacts
    #if emailAdd is not None:
    #    dataStore.updateUser(emailAdd, **{'contacts': contactList})
#    session['contacts'] = contactList

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
    account.post_webhook(**{
        "callback_url": url_for('newMailCallback', _external=True),
        'failure_notif_url': url_for('newMailFailureCallback', _external=True)
    })
    dataStore.updateUser(args['email'], **{'context_id': account.id})
    return account.id

@app.route('/newmail-callback', methods=['POST'])
def newMailCallback():
    print request.json['message_data']['message_id']
    user = dataStore.getUserByContextId(request.json['account_id'])
    account = c.Account(context_io, {'id': request.json['account_id']})
    msg = c.Message(account, { 'message_id': request.json['message_data']['message_id']})
    msg.get(**{'include_body': 1, 'body_type': 'text/html'})
    message = parser.processMessage(user['_id'], msg)
    dataStore.saveMessage(**message)
    return 'OK'

@app.route('/newmail-failure-callback', methods=['POST'])
def newMailFailureCallback():
    print request.json
    return 'OK'

@app.route('/mailbox-sync-callback', methods=['POST'])
def mailboxSyncCallback():
    accountId = request.json['account_id']
    user = dataStore.getUserByContextId(accountId)
    dataStore.updateUser(user['_id'], **{ 'pending_contacts': True, 'pending_sync': False })
    return 'OK'

# sends user info to be our contextio account so that we can later on see their email
@app.route('/sendUserInfo', methods=['POST'])
def sendUserInfo():
    try:
        firstName = request.json["firstName"]
        email = request.json["email"]
        password = request.json["password"]
        # Check if the user exists
        user = dataStore.getUser(email);
        error = 'Invalid credentials: Your username and/or password is incorrect. Please try again.'
        if user != None:
            # Compare password
            if pbkdf2_sha256.verify(password, user["password"]) == True:
                session["context_id"] = user["context_id"]
            else:
                return json.dumps({ 'success': False, 'error': error });
        elif firstName != '':
            user = dataStore.createUser(**{
                '_id': email,
                'firstname': firstName,
                'password': pbkdf2_sha256.encrypt(password, rounds=200000, salt_size=16),
                'contacts': [],
                'pending_sync': False,
                'pending_contacts': False,
                'pending_analysis': False,
                'mailboxes': 0      # Test Ashley
            });
            accountData = {
                'email': email,
                'first_name': firstName
            }
            account = context_io.post_account(**accountData)
            account.post_webhook(**{
                "callback_url": url_for('newMailCallback', _external=True),
                'failure_notif_url': url_for('newMailFailureCallback', _external=True)
            })
            dataStore.updateUser(user['_id'], **{'context_id': account.id})
            session["context_id"] = account.id
        else:
            return json.dumps({ 'success': False, 'error': "User not found, firstname is required to create an account" });
        session["provider_name"] = 'local'
        session["email"] = user['_id']
        session['firstname'] = user['firstname'];
        return json.dumps({ 'success': True, 'user': user['_id'] });
    except Exception as e:
        return json.dumps({ 'success': False, 'error': str(e) });

@app.route('/mailboxcallback', methods=["GET"])
def mailboxCallback():
    print json.dumps(request.args)
    source = context_io.get_connect_tokens(**{ 'token': request.args.get('contextio_token')});
    user = dataStore.getUserByContextId(source['account']['id'])
    dataStore.addUserSource(source['account']['id'], source['email'])
    dataStore.updateUser(user['_id'], **{
        'pending_sync': True
    })
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
        mailboxcount = dataStore.getmailboxcount(session["context_id"])
        add = mailboxcount + 1
        dataStore.updatemailbox(session["context_id"], add)
        return json.dumps(result);

@app.route('/remove-mailbox', methods=["POST"])
def removeMailbox():
    if request.method == 'POST':
        label = request.json["label"]
        account = c.Account(context_io, { 'id': session["context_id"] })
        source = c.Source(account, { 'label': label })
        mailboxcount = dataStore.getmailboxcount(session["context_id"])
        add = mailboxcount - 1
        dataStore.updatemailbox(session["context_id"], add)
        return json.dumps(source .delete());

@app.route('/mailboxes', methods=["GET"])
def mailboxes():
    account = c.Account(context_io, { 'id': session["context_id"] })
    sources = account.get_sources();
    return render_template('mailboxes.html', sources=sources)


# for when user wants to see more contacts, see inbox.html, when press on arrow, grabs how many times arrows has been pressed with js
# and then displays contacts based on count * offset * 10
@app.route('/showMoreContacts', methods=["GET"])
def showMoreContacts():
    user = dataStore.getUser(session['email'])
    mailboxcount = dataStore.getmailboxcount(session["context_id"])
    account = c.Account(context_io, { 'id': session["context_id"] })
    numOfContacts = 30
    contacts = account.get_contacts(limit=numOfContacts)
    contactList = []
    for contactObj in contacts:
        contactList.append(contactObj.email)
    return render_template('moreContacts.html', listOfContacts = contactList, mailboxcount = mailboxcount)

@app.route('/selectContact', methods=["POST"])
def selectContact():
    contactEmail = request.json["email"]
    contactId = session['email'] + '_' + contactEmail
    return json.dumps(dataStore.updateContactStatus(contactId, True))

@app.route('/removeContact', methods=["POST"])
def removeContact():
    user = dataStore.getUser(session['email'])
    contact = request.json['contact']
    #if dataStore.removeUserContact(user['_id'], **contact):
    dataStore.deleteContactData(user['_id'], **contact)
    contactId = session['email'] + '_' + contact['emails'][0]
    dataStore.updateContactStatus(contactId, False)
    return json.dumps(True)

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
    personalityJson = personalityAnalyzer.getProfile(data.encode('utf-8'))
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

# Returns the personality given a email address { email: anEmailAddress }
# Returns the full_personality_json
@app.route('/get-fullBig5', methods=['POST'])
def getFullBig5():
    user = dataStore.getUser(session['email'])
    if(not user['pending_sync'] and not user['pending_contacts'] and not user['pending_analysis']):
        email = request.json['email']
        return json.dumps({ 'name': 'Big 5', 'children': dataStore.getFullBig5(email) })
    else:
        return json.dumps(None)

# Returns the messages sent by a user. Expects { email: anEmailAddress }
@app.route('/get-messages', methods=['POST'])
def getMessagesFromUser():
    user = dataStore.getUser(session['email'])
    if(not user['pending_sync'] and not user['pending_contacts'] and not user['pending_analysis']):
        email = request.json['email'];
        return json.dumps(dataStore.getMessagesFromUser(email))
    else:
        return json.dumps(None)

@app.route('/get-inbox', methods=["GET"])
def getInbox():
    user = dataStore.getUser(session['email'])
    userAccount = c.Account(context_io, { 'id': user["context_id"] })
    # get messages of selected contact
    contacts = dataStore.getContactsByUser(session['email'], True)
    messages = []
    latestDate = 0
    for contact in contacts:
        contactEmail = contact['email']
        messages = messages + userAccount.get_messages(limit=20, include_body=0, email=contactEmail, body_type="text/html")
    result = {
        'msgCount': len(messages),
        'messages': messages
    }
    return json.dumps(result, default=lambda o: o.__dict__)

@app.route('/get-contacts', methods=["GET"])
def getUserContacts():
    result = {}
    contactNames = []
    user = dataStore.getUser(session['email'])

    if dataStore.hasContactsPopulated(session['email']) > 0:
        result = getUserContactsDB()
    else:
        userAccount = c.Account(context_io, { 'id': user["context_id"] })
        contacts = userAccount.get_contacts()
        for contact in contacts:
            contact.get()
            contactDB = {'name': contact.name,
                        'emails': contact.emails,
                        'email': contact.emails[0],
                        'user': session['email'],
                        'is_selected': False,
                        'thumbnail':contact.name,
                        'last_received':contact.last_received,
                        'last_sent':contact.last_sent,
                        'count':contact.count
                        }
            contactNames.append(contact.emails[0])
            contactId = session['email'] + '_' + contact.emails[0]
            print 'contactId %s ', contactId
            dataStore.addContact(contactId, **contactDB )

        result = {
            'contacts': contacts,
            'selectedContacts': []
        }
        session['contacts'] = contactNames
    return json.dumps(result, default=lambda o: o.__dict__)

@app.route('/get-contacts-db', methods=["GET"])
def getUserContactsDB():
    contacts = dataStore.getContactsByUser(session['email'])
    selectedContacts =[]
    allContacts = []
    contactNames = []
    print 'Calling get-contacts-from-db'
    for contact in contacts:
        if contact['is_selected'] == True:
            selectedContacts.append(contact)
            contactNames.append(contact['emails'][0])
        allContacts.append(contact)

    result = {
        'contacts': allContacts,
        'selectedContacts': selectedContacts
    }
    session['email'] = contactNames
    return json.dumps(result)


@app.route('/get-selected-contacts', methods=["GET"])
def getSelectedContacts():
    selectedContacts = []
    contacts = dataStore.getContactsByUser(session['email'], True)
    for contact in contacts:
        if contact['is_selected'] == True:
            selectedContacts.append(contact)
    return json.dumps(selectedContacts)

@app.route('/check-status', methods=["GET"])
def checkStatus():
    user = dataStore.getUser(session['email'])
    # The following is a hack to get around limitation with callbacks to localhost
    if(user['pending_sync']): #and 'localhost' in url_for('inbox', _external=True)):
        params = {
            'id': user["context_id"]
        }
        account = c.Account(context_io, params)
        sources = account.get_sync()
        isOkay = False
        # The format of the response is awful so the following is as good as I could get
        for source in sources:
            if(sources[source] != None):
                for sync in sources[source]:
                    if(sources[source][sync]['initial_import_finished'] == True):
                        isOkay = True
        if(isOkay):
            dataStore.updateUser(user['_id'], **{ 'pending_sync': False, 'pending_contacts': True, 'pending_analysis': False })
            user['pending_contacts'] = True
            user['pending_sync'] = False
    # End of localhost hack
    return json.dumps({
        'pending_sync': user['pending_sync'],
        'pending_contacts': user['pending_contacts'],
        'pending_analysis': user['pending_analysis']
    })

@app.route('/get-tone', methods=["GET", "POST"])
def getTone():
    if('to' in request.json):
        to = request.json['to']
        userTone = dataStore.getContactToneBySenderAndReceiver(session['email'], to)
        # print userTone
    else:
        userTone = dataStore.getContactToneBySender(session['email'])
        # print userTone
    return json.dumps(userTone)

@app.route('/get-user-tone', methods=["GET", "POST"])
def getUserTone():
    userTone = dataStore.getContactToneBySender(session['email'])
    return json.dumps(userTone)

@app.route('/get-relationships', methods=["GET", "POST"])
def getRelationships():
    relationships = dataStore.getRelationshipsForUser(session['email'])
    return json.dumps(relationships)

@app.route('/show-personality', methods=["GET"])
def showPersonality():
    return render_template('personality.html')

@app.route('/show-msg-tone', methods=["GET"])
def showMsgTone():
    return render_template('mail.html')

@app.route('/show-tone', methods=["GET"])
def showTone():
    return render_template('tone.html')

@app.route('/personality-dashboard', methods=["GET"]) #Ashley Test
def showPersonalityDashboard():
    mailboxcount = dataStore.getmailboxcount(session["context_id"])
    return render_template('personality-dashboard.html', mailboxcount = mailboxcount)



@app.route('/tone-dashboard', methods=["GET"])
def showToneDashboard():
    mailboxcount = dataStore.getmailboxcount(session["context_id"])
    return render_template('tone-dashboard.html', mailboxcount = mailboxcount)

# Returns individual message.  Expects { messageId: messageId}
#@app.route('/get-message', methods=['POST'])
#def getMessage():
#    email = request.form['messageId'];
#    return datastore.getMessage(**{'messageId':messageId})

# Returns a list of CONTACT information given a USER email. Expects {email: anEmailAddress }
#@app.route('/get-user-contact-analysis', methods=['POST'])
    #email = request.form['email']  # email is the USER
    #return dataStore.getInfoForContacts(email)

    # Get messages from the mongodb where the from = email

@app.route('/enable', methods=["POST"])
def enable():
    if request.method == 'POST':
        label = request.json["label"]
        account = c.Account(context_io, { 'id': session["context_id"]})
        source = c.Source(account, { 'label': label , 'status' : 1 })
        logger.info(source)
        return json.dumps(source)

@app.route('/delete', methods=['POST', 'GET'])
def removeAccount():
    #Need to rewrite this. Too long and not using DRY
    removed = ' Your account has been successfully deleted. We hope to see you again.'
    error = 'Oops, something went wrong when trying to delete your account. Please contact knowus.io'
    try:
        dbremove = dataStore.delete_account(session["context_id"])
        account = c.Account(context_io, { 'id': session["context_id"]})
        del_acct = account.delete()
        logger.info('{0} account has been deleted from contextio'.format(session["context_id"]))
        session.clear()
        return render_template('userLogin.html',error=removed)
    except:
        logger.error('App encountered an issue with account: {0} when trying to delete it.'.format(session["context_id"]))
        session.clear()
        return render_template('userLogin.html',error=error)

#####################################################################
# START Enron Specific Functions NB should be in separate file/class
######################################################################

@app.route('/enron-demo', methods=["POST", "GET"])
def enronDemo():
    return render_template('enron-demo.html')

@app.route('/enron-inbox/<email>', methods=['POST'])
def enronInbox1(email):
    session['enronEmail'] = email
    return 'OK'
    
    #return json.dumps(result, default=lambda o: o.__dict__)

@app.route('/enron-inbox', methods=['GET','POST'])
def enronInbox():
    if request.method == 'GET':
        email = session['enronEmail']
        user = dataStore.getUser(email)
        print user
        contacts = dataStore.getContactsByUser(email, True)
        messages = []
        latestDate = 0
        uMessages = dataStore.getMessagesFromUser(email)
        messages = uMessages[email]
        for contact in contacts:
            contactEmail = contact['email']
            cMessages = dataStore.getMessagesFromUser(contactEmail)
            messages = messages + cMessages[contactEmail]
        result = {
        'msgCount': len(messages),
        'messages': messages
        }
    return render_template('enron-inbox.html')

@app.route('/enron-get-inbox', methods=["GET"])
def enronGetInbox():
    email = session['enronEmail']
    user = dataStore.getUser(email)
    contacts = dataStore.getContactsByUser(email, True)
    messages = []
    latestDate = 0
    uMessages = dataStore.getMessagesFromUser(email)
    messages = uMessages[email]
    for contact in contacts:
        contactEmail = contact['email']
        cMessages = dataStore.getMessagesFromUser(contactEmail)
        messages = messages + cMessages[contactEmail]
    result = {
        'msgCount': len(messages),
        'messages': messages
    }
    return json.dumps(result, default=lambda o: o.__dict__)

@app.route('/enron-personality-dashboard', methods=["GET"]) 
def showPersonalityDashboardEnron():
    return render_template('enron-personality-dashboard.html')

@app.route('/enron-get-fullBig5', methods=['POST'])
def enronGetFullBig5():
    user = dataStore.getUser(session['enronEmail'])
    email = request.json['email']
    print 'email for full big 5', email
    return json.dumps({ 'name': 'Big 5', 'children': dataStore.getFullBig5(email) })
     

@app.route('/enron-get-selected-contacts', methods=["GET"])
def enronGetSelectedContacts():
    selectedContacts = []
    contacts = dataStore.getContactsByUser(session['enronEmail'], True)
    for contact in contacts:
        if contact['is_selected'] == True:
            selectedContacts.append(contact)
    return json.dumps(selectedContacts)

@app.route('/enron-get-tone', methods=["GET", "POST"])
def enronGetTone():
    if('to' in request.json):
        to = request.json['to']
        userTone = dataStore.getContactToneBySenderAndReceiver(session['enronEmail'], to)
        # print userTone
    else:
        userTone = dataStore.getContactToneBySender(session['enronEmail'])
        # print userTone
    return json.dumps(userTone)

@app.route('/enron-tone-dashboard', methods=["GET"])
def enronShowToneDashboard():
    return render_template('enron-tone-dashboard.html')

@app.route('/enron-logout', methods=["GET"])
def enronLogout():
    session.clear();
    return redirect(url_for('enron-demo'))

####### END ENRON (NB sshould be in separate file/class ##########    

if __name__ == "__main__":
    app.run(host='127.0.0.1',port=5000,debug=True)
