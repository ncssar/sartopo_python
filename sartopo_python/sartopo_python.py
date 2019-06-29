# #############################################################################
#
#  sartopo_python.py - python interfaces to the sartopo API
#
#   developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2018 Tom Grundy
#
#   Sartopo / Caltopo currently does not have a publicly available API;
#    this code calls the non-publicized API that could change at any time.
#
#   This module is intended to provide a simple, API-version-agnostic sartopo
#    interface to other applications.
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
# 11-19-18    TMG        clean up for first package release
#  6-29-18    TMG        add getFeatures to return a list of map features with IDs;
#                          move an existing marker by specifying existing marker ID
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
    
    def sendRequest(self,type,apiUrlEnd,j,id="",returnJson=None):
        if self.apiVersion<0:
            print("sartopo session is invalid; request aborted: type="+str(type)+" apiUrlEnd="+str(apiUrlEnd))
            return -1
        apiUrlEnd=apiUrlEnd.lower()
        if self.apiVersion>0:
            apiUrlEnd=apiUrlEnd.capitalize()
        if apiUrlEnd.startswith("Since"): # 'since' must be lowercase even in API v1
            apiUrlEnd=apiUrlEnd.lower()
        url="http://"+self.domainAndPort+self.apiUrlMid+apiUrlEnd+"/"+id
        url=url.replace("[MAPID]",self.mapID)
#         print("sending "+str(type)+" to "+url)
        if type is "post":
#             print("SENDING POST:")
#             print(json.dumps(j,indent=3))
            r=self.s.post(url,data={'json':json.dumps(j)},timeout=2)
        elif type is "get": # no need for json in GET; sending null JSON causes downstream error
            r=self.s.get(url,timeout=2)
        else:
            print("Unrecognized request type:"+str(type))
            return -1
#         print("response code = "+str(r.status_code))
#         print("response:")
#         try:
#             print(json.dumps(r.json(),indent=3))
#         except:
#             print(r.text)
        if returnJson:
            try:
                rj=r.json()
            except:
                print("response had no decodable json")
                return -1
            else:
                if returnJson=="ID":
                    id=None
                    if 'result' in rj and 'id' in rj['result']:
                        id=rj['result']['id']
                    elif 'id' in rj:
                        id=rj['id']
                    else:
                        print("No valid folder ID was returned from the request.")
                    return id
                if returnJson=="ALL":
                    return rj
        
    def addFolder(self,label="New Folder"):
        j={}
        j['properties']={}
        j['properties']['title']=label
        return self.sendRequest("post","folder",j,returnJson="ID")
    
    def addMarker(self,lat,lon,title="New Marker",description="",color="#FF0000",symbol="point",rotation=None,folderId=None,existingId=""):
        j={}
        jp={}
        jg={}
        jp['class']='Marker'
        jp['updated']=0
        jp['marker-color']=color
        jp['marker-symbol']=symbol
        jp['title']=title
        if folderId:
            jp['folderId']=folderId
        jp['description']=description
        jg['type']='Point'
        jg['coordinates']=[float(lon),float(lat)]
        j['properties']=jp
        j['geometry']=jg
        j['type']='Feature'
        if existingId:
            j['id']=existingId
#         print("sending json: "+json.dumps(j.json(),indent=3))
        return self.sendRequest("post","marker",j,id=existingId,returnJson="ID")

    def getFeatures(self,featureClass=None,since=0):
        rj=self.sendRequest("get","since/"+str(since),None,returnJson="ALL")
        if not featureClass:
            return rj # if no feature class is specified, return the entire json response
        else:
            rval=[]
            if 'result' in rj and 'state' in rj['result'] and 'features' in rj['result']['state']:
                features=rj['result']['state']['features']
                for feature in features:
                    id=feature['id']
                    prop=feature['properties']
                    if prop['class']==featureClass:
                        title=prop['title']
#                         print(featureClass+": title='"+title+"'  id="+str(id))
                        rval.append([title,id])
            return rval
    

# if __name__ == "__main__":
#     sts=SartopoSession("localhost:8080","SBH")
#     sts.addMarker("39","-120","stuff")
#     r=sts.getFeatures("Marker")
#     print("sending with id:"+r[0][1])
#     sts.addMarker("39.2536","-121.0267",r[0][0],existingId=r[0][1])
    
        