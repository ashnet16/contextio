import os
import json

#Routings go here

from flask import Flask, render_template, request, url_for
import contextio as c
#from pymongo import Connection
#import json
#from bson import json_util
#from bson.json_util import dumps

app = Flask(__name__)

#MONGODB_HOST = 'localhost'
#MONGODB_PORT = 27017
#DBS_NAME = 'donorschoose'
#COLLECTION_NAME = 'projects'
#FIELDS = {'school_state': True, 'resource_type': True, 'poverty_level': True, 'date_posted': True, 'total_donations': True, '_id': False}


# contextio key and secret key
#CONSUMER_KEY = 'l57sr7jp'
#CONSUMER_SECRET = 'm0mRv5iaojsNWnvu'

#context_io = c.ContextIO(
   # consumer_key=CONSUMER_KEY,
   # consumer_secret=CONSUMER_SECRET)

@app.route('/')
def index():
        return render_template('userLogin.html')

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
