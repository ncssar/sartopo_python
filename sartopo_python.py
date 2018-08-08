# #############################################################################
#
#  sartopo_python.py - python interfaces to the sartopo API
#
#   developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2018 Tom Grundy
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
#
#-----------------------------------------------------------------------------

import requests
import json
    
class SartopoSession():
    def __init__(self):
        self.s=requests.session()
        self.mapID="178U"
        self.domainAndPort="localhost:8080"
        self.determineAPIVersion()
        
    def determineAPIVersion(self):
        # by default, do not assume any sartopo session is running;
        # send a GET request to http://localhost:8080/api/v1/map/
        #  response code 200 = new API
        #  otherwise:
        #    send a GET request to http://localhost:8080/rest/
        #     response code 200 = old API
        
        self.apiVersion=-1
        self.apiUrlMid="/invalid/"
        url="http://"+self.domainAndPort+"/api/v1/map/"
        print("searching for API v1: sending get to "+url)
        try:
            r=self.s.get(url,timeout=2)
        except:
            print("no response from first get request")
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
    
    def post(self,apiUrlEnd,j):
        url="http://"+self.domainAndPort+self.apiUrlMid+apiUrlEnd
        url=url.replace("[MAPID]",self.mapID)
        print("sending post to "+url)
        r=self.s.post(url,data={'json':json.dumps(j)},timeout=2)
        print("response code = "+str(r.status_code))
        print("response text = "+r.text)
        
    def addMarker(self,lat,lon,label="New Marker",folderId=None,url="",comments=""):
        j={}
        j['label']=label
        j['folderId']=folderId
        j['url']=url
        j['comments']=comments
        j['position']={"lat":lat,"lng":lon}
        self.post("marker/",j)
        
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

def main():
    sts=SartopoSession()
    sts.addMarker(39,-120)
    
if __name__ == '__main__':
    main()

    
    