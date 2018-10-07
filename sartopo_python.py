# #############################################################################
#
#  sartopo_python.py - python interfaces to the sartopo API
#
#   developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2018 Tom Grundy
#
#   Sartopo / Caltopo currently does not have a publically available API;
#    this code calls the non-publicized API that could change at any time.
#
#   This module is intended to provide a simple, API-version-agnostic sartopo
#    interface to other appliactions.
#
#   Initially, this is just a module and not a package, so, just place this
#    file directly in your module search path (not in a subdirectory).
#    
#   This python code is in no way supported or maintained by caltopo LLC
#    or the authors of caltopo.com or sartopo.com.
#
#  www.github.com/ncssar/sartopo_python
#
#  Contact the author at nccaves@yahoo.com
#   Attribution, feedback, bug reports and feature requests are appreciated
#
#  REVISION HISTORY
#-----------------------------------------------------------------------------
#   DATE   |  AUTHOR  |  NOTES
#-----------------------------------------------------------------------------
#  8-29-18    TMG        First version - creates folders and markers
#  10-7-18    TMG        allow session on network other than localhost; allow
#                           three-character mapID; overhaul to work with
#                           significant api changes in v4151 of sar.jar -
#                           probably not backwards compatible; will require
#                           changes to code that calls these functions
#
#-----------------------------------------------------------------------------

import requests
import json
    
class SartopoSession():
    def __init__(self,domainAndPort="localhost:8080",mapID=None):
        self.s=requests.session()
        self.apiVersion=-1
        if not mapID or not isinstance(mapID,str) or len(mapID)<3:
            print("ERROR: you must specify a three-or-more-character sartopo map ID string (end of the URL) when opening a SartopoSession object.")
            return
        self.mapID=mapID
        self.domainAndPort=domainAndPort
        self.setupSession()
        
    def setupSession(self):
        # by default, do not assume any sartopo session is running;
        # send a GET request to http://localhost:8080/api/v1/map/
        #  response code 200 = new API
        #  otherwise:
        #    send a GET request to http://localhost:8080/rest/
        #     response code 200 = old API
        
        self.apiUrlMid="/invalid/"
        url="http://"+self.domainAndPort+"/api/v1/map/"
        print("searching for API v1: sending get to "+url)
        try:
            r=self.s.get(url,timeout=2)
        except:
            print("no response from first get request; aborting; should get a response of 400 at this point for api v0")
        else:
            print("response code = "+str(r.status_code))
            if r.status_code==200:
                self.apiVersion=1
                self.apiUrlMid="/api/v1/map/[MAPID]/"
            else:
                url="http://"+self.domainAndPort+"/rest/marker/"
                print("searching for API v0: sending get to "+url)
                try:
                    r=self.s.get(url,timeout=2)
                except:
                    print("no response from second get request")
                else:
                    print("response code = "+str(r.status_code))
                    if r.status_code==200:
                        self.apiVersion=0
                        self.apiUrlMid="/rest/"
                        # for v0, send a get to the map URL to authenticate the session
                        url="http://"+self.domainAndPort+"/m/"+self.mapID
                        print("sending API v0 authentication request to url "+url)
                        try:
                            r=self.s.get(url,timeout=2)
                        except:
                            print("no response during authentication for API v0")
                        else:
                            print("response code = "+str(r.status_code))
                            if r.status_code==200:
                                print("API v0 session is now authenticated")
        print("API version:"+str(self.apiVersion))
    
    def post(self,apiUrlEnd,j,returnJsonResponse=False):
        apiUrlEnd=apiUrlEnd.lower()
        if self.apiVersion>0:
            apiUrlEnd=apiUrlEnd.capitalize()
        url="http://"+self.domainAndPort+self.apiUrlMid+apiUrlEnd+"/"
        url=url.replace("[MAPID]",self.mapID)
        print("sending post to "+url)
        r=self.s.post(url,data={'json':json.dumps(j)},timeout=2)
        print("response code = "+str(r.status_code))
        print("response text = "+r.text)
        if returnJsonResponse:
            return r.json()
    
    def addFolder(self,label="New Folder"):
        if self.apiVersion<0:
            print("sartopo session is invalid; addFolder aborted")
            return -1
        j={}
        j['properties']={}
        j['properties']['title']=label
        rj=self.post("folder",j,True)
        id=None
        if 'result' in rj and 'id' in rj['result']:
            id=rj['result']['id']
        elif 'id' in rj:
            id=rj['id']
        else:
            print("No valid folder ID was returned from the request.")
        return id
    
    def addMarker(self,lat,lon,title="New Marker",description="",color="FF0000",symbol="point",rotation=None,folderId=None):
        if self.apiVersion<0:
            print("sartopo session is invalid; addMarker aborted")
            return -1
        j={}
        jp={}
        jg={}
        jp['marker-color']=color
        jp['marker-symbol']=symbol
        jp['title']=title
        jp['folderId']=folderId
        jp['description']=description
        jg['coordinates']=[lon,lat]
        j['properties']=jp
        j['geometry']=jg
#         print("sending json: "+str(j))
        self.post("marker",j)
        
# def getMapJson(mapID):
#     domainAndPort="localhost:8080"
# #     url="http://"+domainAndPort+"/m/"+mapID
#     # new API: send a GET to domainAndPort/api/v1/map/<mapID>/since/<timestamp>
#     url="http://"+domainAndPort+"/api/v1/map/"+mapID+"/since/"+ts
#     s=requests.session()
#     try:
#         r=s.get(url)
#     except:
#         return("ERROR: did not get any resposnse from a GET request to "+url)
#     else:
#         # OLD API: the response is a bunch of HTML including the json;
#         #   get the whole thing and find org.sarsoft.preload
#         # pattern explanation: get the largest complete { } set following
#         #   (but not including) org.sarsoft.preload
#         # (?<=  -  positive lookbehind assertion: the pattern until close
#         #   parens must exist in order to match, but will not be part of the
#         #   return value
#         # .*?   -  any characters, non-greedy (i.e. match until the first semicolon;
#         #            normally this is greedy and will match until the last semicolon
#         # (?=   -  positive lookahead assertion: the pattern until close parens
#         #   must exist in order to match, but will not be part of the return value
# #         re.search("(?<=org.sarsoft.preload = ).*?(?=;)",str(r.content)).group()
#         # new API: the response is json
#         return(json.loads(r.content.decode(encoding='UTF-8')))
    
# getMapObjectInfo - return a table of 
# def getMapObjectInfo(label):


    
    