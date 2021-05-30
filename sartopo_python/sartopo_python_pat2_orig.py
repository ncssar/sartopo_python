# #############################################################################
#
#  sartopo_python.py - python interfaces to the sartopo API
#
#   developed for Nevada County Sheriff's Search and Rescue
#    Copyright (c) 2020 Tom Grundy
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
############################################################
#
# EXAMPLES:
#
#     from sartopo_python import SartopoSession
#     import time
#     
#     sts=SartopoSession("localhost:8080","<offlineMapID>")
#     fid=sts.addFolder("MyFolder")
#     sts.addMarker(39,-120,"stuff")
#     sts.addMarker(39.01,-120.01,"myStuff",folderId=fid)
#     r=sts.getFeatures("Marker")
#     print("r:"+str(r))
#     print("moving the marker after a pause:"+r[0]['id'])
#     time.sleep(5)
#     sts.addMarker(39.02,-120.02,r[0]['properties']['title'],existingId=r[0]['id'])
#     
#     sts2=SartopoSession(
#         "sartopo.com",
#         "<onlineMapID>",
#         configpath="../../sts.ini",
#         account="<accountName>")
#     fid2=sts2.addFolder("MyOnlineFolder")
#     sts2.addMarker(39,-120,"onlineStuff")
#     sts2.addMarker(39.01,-119.99,"onlineStuff2",folderId=fid2)
#     r2=sts2.getFeatures("Marker")
#     print("return value from getFeatures('Marker'):")
#     print(json.dumps(r2,indent=3))
#     time.sleep(15)
#     print("moving online after a pause:"+r2[0]['id'])
#     sts2.addMarker(39.02,-119.98,r2[0]['properties']['title'],existingId=r2[0]['id'])
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
#  6-29-19    TMG        add getFeatures to return a list of map features with IDs;
#                          move an existing marker by specifying existing marker ID
#   7-3-19    TMG        return folderId, if it exists, with each feature returned
#                          by getFeatures, to allow filtering by folder; modify
#                          setupSession to only return API version 1 if the
#                          API is version 1 AND the map ID is valid
#  3-30-20    TMG        fix #3: v1.0.6: change the return value structure from getFeatures
#                          to return the entire json structure for each feature;
#                          this enables preservation of marker-symbol when moving
#                          an existing marker
#  5-30-20    TMG        fix #2: v1.1.0: send signed requests to sartopo.com (online)
#   6-2-20    TMG        v1.1.1: fix #5 (use correct meaning of 'expires');
#                           fix #6 (__init__ returns None on failure)
#
#-----------------------------------------------------------------------------

import hmac
import base64
import requests
import json
import configparser
import os
import time

class SartopoSession():
    def __init__(self,domainAndPort="localhost:8080",mapID=None,ext=None,configpath=None,account=None,id=None,key=None):
        self.s=requests.session()
        self.apiVersion=-1
        print("IN SARTOPO SESSION")
        if not mapID or not isinstance(mapID,str) or len(mapID)<3:
            print("ERROR: you must specify a three-or-more-character sartopo map ID string (end of the URL) when opening a SartopoSession object.")
            return None
        self.mapID=mapID
        self.domainAndPort=domainAndPort
        # configpath, account, id, and key are used to build
        #  signed requests for sartopo.com
        self.configpath=configpath
        self.account=account
        self.id=id
        self.key=key
        self.ext=ext
        self.setupSession()
        
    def setupSession(self):
        if "sartopo.com" in self.domainAndPort.lower():
            id=None
            key=None
            # if configpath and account are specified,
            #  conigpath must be the full pathname of a configparser-compliant
            #  config file, and account must be the name of a section within it,
            #  containing keys 'id' and 'key'.
            # otherwise, those parameters must have been specified in this object's
            #  constructor.
            # if both are specified, first the config section is read and then
            #  any parameters of this object are used to override the config file
            #  values.
            # if any of those three values are still not specified, abort.
            if self.configpath is not None:
                if os.path.isfile(self.configpath):
                    if self.account is None:
                        print("config file '"+self.configpath+"' is specified, but no account name is specified.")
                        return -1
                    config=configparser.ConfigParser()
                    config.read(self.configpath)
                    if self.account not in config.sections():
                        print("specified account '"+self.account+"' has no entry in config file '"+self.configpath+"'.")
                        return -1
                    section=config[self.account]
                    id=section.get("id",None)
                    key=section.get("key",None)
                    if id is None or key is None:
                        print("account entry '"+self.account+"' in config file '"+self.configpath+"' is not complete:\n  it must specify id and key.")
                        return -1
                else:
                    print("specified config file '"+self.configpath+"' does not exist.")
                    return -1

            # now allow values specified in constructor to override config file values
            if self.id is not None:
                id=self.id
            if self.key is not None:
                key=self.key
            # finally, save them back as parameters of this object
            self.id=id
            self.key=key

            if self.id is None:
                print("sartopo session is invalid: 'id' must be specified for online maps")
                return -1
            if self.key is None:
                print("sartopo session is invalid: 'key' must be specified for online maps")
                return -1

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
                # now validate the mapID, since the initial test doesn't care about mapID
                mapUrl="http://"+self.domainAndPort+"/m/"+self.mapID
                try:
                    r=self.s.get(mapUrl,timeout=2)
                except:
                    print("API version 1 detected, but the mapID is not valid:"+mapUrl+":")
                else:
                    print("DATA:"+str(r))
                    if r.status_code==200:
                        # now we know the API is valid and the mapID is valid
                        self.apiVersion=1
                        self.apiUrlMid="/api/v1/map/[MAPID]/"
                    else:
                        print("API version 1 detected, but the map-specific URL returned a code of "+str(r.status_code)+" so this session is not valid.")
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
                        url="http://"+self.domainAndPort+"/m/"+self.mapID ## +self.ext
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
        
    def sendRequest(self,typex,apiUrlEnd,j,id="",returnJson=None):
        if self.apiVersion<0:
            print("sartopo session is invalid; request aborted: type="+str(typex)+" apiUrlEnd="+str(apiUrlEnd))
            return -1
        apiUrlEnd=apiUrlEnd.lower()
        if self.apiVersion>0:
            apiUrlEnd=apiUrlEnd.capitalize()
        if apiUrlEnd.startswith("Since"): # 'since' must be lowercase even in API v1
            apiUrlEnd=apiUrlEnd.lower()
        # append id (if any) to apiUrlEnd so that it is a part of the request
        #  destination and also a part of the pre-hased data for signed requests
        if id!="": # sending online request with slash at the end causes failure
            apiUrlEnd=apiUrlEnd
            apiUrlEnd=apiUrlEnd+"/"+str(id)
        mid=self.apiUrlMid.replace("[MAPID]",self.mapID) ## +self.ext)
        url="http://"+self.domainAndPort+mid+apiUrlEnd
        print("sending "+str(typex)+" to "+url)
        if typex is "post":
            params={}
            params["json"]=json.dumps(j)
            if "sartopo.com" in self.domainAndPort.lower():
                expires=int(time.time()*1000)+120000 # 2 minutes from current time, in milliseconds
                data="POST "+mid+apiUrlEnd+"\n"+str(expires)+"\n"+json.dumps(j)
                # print("pre-hashed data:"+data)                
                token=hmac.new(base64.b64decode(self.key),data.encode(),'sha256').digest()
                token=base64.b64encode(token).decode()
#                 print("hashed data:"+str(token))
                params["id"]=self.id
                params["expires"]=expires
                params["signature"]=token
                # print("SENDING POST to '"+url+"':")
                # print(json.dumps(params,indent=3))
                # print("Key:"+str(self.key))
            r=self.s.post(url,data=params,timeout=2)
            print("Ris:"+str(r))
        elif typex is "get": # no need for json in GET; sending null JSON causes downstream error
#             print("SENDING GET to '"+url+"':")
            r=self.s.get(url,timeout=2)
        elif typex is "delete":
            params={}
            if "sartopo.com" in self.domainAndPort.lower():
                expires=int(time.time()*1000)+120000 # 2 minutes from current time, in milliseconds
                data="DELETE "+mid+apiUrlEnd+"\n"+str(expires)+"\n"  #last newline needed as placeholder for json
                print("pre-hashed data:"+data)                
                token=hmac.new(base64.b64decode(self.key),data.encode(),'sha256').digest()
                token=base64.b64encode(token).decode()
#                 print("hashed data:"+str(token))
                params["json"]=''   # no body, but is required
                params["id"]=self.id
                params["expires"]=expires
                params["signature"]=token
                print("SENDING DELETE to '"+url+"':")
                print(json.dumps(params,indent=3))
                print("Key:"+str(self.key))
            r=self.s.delete(url,params=params,timeout=2)   ## use params for query vs data for body data
            print("URL:"+str(url))
            print("Ris:"+str(r))
        else:
            print("Unrecognized request type:"+str(typex))
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
                    print(json.dumps(rj,indent=3))
                    id=None
                    if 'result' in rj and 'id' in rj['result']:
                        id=rj['result']['id']
                    elif 'id' in rj:
                        id=rj['id']
                    elif not rj['result']['state']['features']:  # response if no new info
                        return 0
                    elif 'result' in rj and 'id' in rj['result']['state']['features'][0]:
                        id=rj['result']['state']['features'][0]['id']
                    else:
                        print("No valid ID was returned from the request:")
                        print(json.dumps(rj,indent=3))
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
        #print("sending json: "+json.dumps(j,indent=3))
        return self.sendRequest("post","marker",j,id=existingId,returnJson="ID")

    def addIncTrack(self,cnt,points,startTrack,title="New Track",since=0,description="",folderId=None,existingId=""):
        j={}
        jp={}
        jg={}
        jp['class']='AppTrack'
        jp['updated']=int(time.time()*1000)
        jp['title']=title
        ##########################jp['nop']=True
        if folderId:
            jp['folderId']=folderId
        jp['description']=description
        jg['type']='LineString'
        jg['coordinates']=points
        jg['incremental']=True
        jg['size']=cnt       # cnt includes number of coord in this call
        j['properties']=jp
        j['geometry']=jg
        j['type']='Feature'
        if 0 == 1:      ## set for no existing ID
        ###if existingId:
            j['id']=existingId   # get ID from first call - using Shape
        else:
            existingId = ""
        #print("sending json: "+json.dumps(j,indent=3))
        #print("ID:"+str(existingId))
        if 1 == 1:
        ##if startTrack == 1:
            print("At request first time track"+str(existingId)+":"+str(j))
            return self.sendRequest("post","Shape",j,id=str(existingId),returnJson="ID")
        else:
            print("At request adding points to track:"+str(existingId)+":"+str(since)+":"+str(j))
            return self.sendRequest("post","since/"+str(since),j,id=str(existingId),returnJson="ID")

    def delMarker(self,existingId=""):
        return self.sendRequest("delete","marker",None,id=existingId,returnJson="ALL")


    def delObject(self,objType,existingId=""):
        print("In delete:"+objType+":"+str(existingId))
        ###return self.sendRequest("delete","since/0",None,id=str(existingId),returnJson="ALL")
        return self.sendRequest("delete",objType,None,id=str(existingId),returnJson="ALL")


    def getFeatures(self,featureClass=None,since=0):
        rj=self.sendRequest("get","since/"+str(since),None,returnJson="ALL")
        if not featureClass:
            return rj # if no feature class is specified, return the entire json response
        else:
            rval=[]
            if 'result' in rj and 'state' in rj['result'] and 'features' in rj['result']['state']:
                features=rj['result']['state']['features']
                for feature in features:
#                     print("FEATURE:"+str(feature))
#                     id=feature['id']
                    prop=feature['properties']
                    if prop['class']==featureClass:
                        rval.append(feature) # return the entire json object
#                         rval.append([id,prop]) # return all properties
                        
            return rval