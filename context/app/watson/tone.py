import requests
import json

requests.packages.urllib3.disable_warnings()

class ToneAnalyzerService:
    """Wrapper on the Tone Analyzer service"""

    def __init__(self, vcapServices):
        """
        Construct an instance. Fetches service parameters from VCAP_SERVICES
        runtime variable for Bluemix, or it defaults to local URLs.
        """

        # Local variables
        self.url = "https://gateway.watsonplatform.net/tone-analyzer-experimental/api"
        self.username = "4593f424-a0d9-4ed7-9e33-b211f955cff2"
        self.password = "Eitk33rFdTrg"

        if vcapServices is not None:
            print("Parsing VCAP_SERVICES")
            services = json.loads(vcapServices)
            svcName = "tone_analyzer"
            if svcName in services:
                print("Tone Insights Analyzer found!")
                svc = services[svcName][0]["credentials"]
                self.url = svc["url"]
                self.username = svc["username"]
                self.password = svc["password"]
            else:
                print("ERROR: The Tone Analyzer service was not found")

    def getTone(self, text):
        """Returns the profile by doing a POST to /v1/tone with text"""

        if self.url is None:
            raise Exception("No Tone Analyzer service is bound to this app")
        response = requests.post(self.url + "/v1/tone",
                          auth=(self.username, self.password),
                          headers = {"content-type": "text/plain"},
                          data=text
                          )
        try:
            return json.loads(response.text)
        except:
            raise Exception("Error processing the request, HTTP: %d" % response.status_code)

    def getSynonym(self, words, limit):
        """Returns the profile by doing a POST to /v1/synonym with text"""

        if self.url is None:
            raise Exception("No Tone Analyzer service is bound to this app")
        data = {}
        data['words'] = [words];
        data['limit'] = limit;
        json_data = json.dumps(data)
        response = requests.post(self.url + "/v1/synonym",
                          auth=(self.username, self.password),
                          headers = {"content-type": "application/json"},
                          data=json_data
                          )
        try:
            return json.loads(response.text)
        except:
            raise Exception("Error processing the request, HTTP: %d" % response.status_code)
