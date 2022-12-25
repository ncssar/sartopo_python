# sartopo_python

Sartopo / Caltopo currently does not have a publically available API;
 this code calls the non-publicized API that could change at any time.

This module is intended to provide a simple, API-version-agnostic sartopo
 interface to other appliactions.

This python code is in no way supported or maintained by caltopo LLC
 or the authors of caltopo.com or sartopo.com.

## New for v1.1.0. 5-30-2020:
Signed requests for online maps are now supported.  The same requests that work here for offline maps are now also working for online maps.  See the signed request explanation at the bottom of this README file.

## New for v1.0.6 3-30-2020:
getFeatures now returns the entire json object for each feature.  The top level keys should be id, geometry, and properties.  This allows preservation of things like marker-symbol, folder, coordinates, and so on when moving an existing marker.

## Installation:
```
pip install sartopo_python
```

## Provided functions in class SartopoSession:
### \_\_init\_\_ - create a new session
- domainAndPort="localhost:8080" ('sartopo.com' will require signed requests - see details below)
- mapID=None - three- or four-character map ID [required]
- configPath=None - only needed for signed requests
- account=None - only needed for signed requests
- id=None - only needed for signed requests
- key=None - only needed for signed requests
- sync=True - if True, the session will automatically sync at the specified interval, so .mapData will be kept up to date
 
 NOTE: the following arguments are only relevant if sync=True
 
- syncInterval=5 - interval (in seconds) between automatic sync requests
- syncTimeout=2 - time after which an error will be thrown if no response is received
- syncDumpFile=None - file to which all sync activity will be logged
- propUpdateCallback=None - callback function to be called whenever a feature's properties have been changed
  - called with arguments (id, properties[json])
- geometryUpdateCallback=None - callback function to be called whenever a feature's geometry has been changed
  - called with arguments (id, geometry[json])
- newObjectCallback=None - callback function to be called whenever a new feature has been added
  - called with arguments (feature[json])
- deletedObjectCallback=None - callback function to be called whenever a feature has been deleted
  - called with arguments (id of deleted object, updated list of all features)

### start() - start syncing
- also sets .sync=True
### stop() - stop syncing
- also sets .sync=False
### addFolder(label="New Folder", queue=False) - create a SARTopo folder
- creates a new folder with the specified name; queues the request if specified (see queueing below)
### addMarker - create a SARTopo marker
- lat
- lon
- title="New Marker"
- description=""
- color="FF0000"
- symbol="point"
- rotation=None
- folderId=None
- (beginning in 1.0.4) existingId="" - specify this to edit an existing marker
### addLine - add a line object
### addLineAssignment - add a line assignment object
### addAreaAssignment - add an area assignment object
### flush - send all queued requests
### addAppTrack - add an appTrack object
### delMarker - delete a marker
### getFeatures(featureClass=None, since=0, timeout=2) - get a list of map features
- returns a list of json of all features that meet the featureClass and since filters
### editObject - edit an existing object

## Geometry operations:

For the following geometry operations, the arguments can be
  title (string), id (string), or feature (json)
  
Also, the arguments can refer either to assignments or to non-assignment objects.

### cut - notch or slice a polygon or line, using a polygon or line
- can accomodate the following operations:
  - remove a notch from a polygon, using a polygon
  - slice a polygon, using a polygon
  - slice a polygon, using a line
  - slice a line, using a polygon
  - slice a line, using a line

### expand - expand the first polygon to include the area of the second polygon

### crop - remove portions of a line or polygon that are outside a boundary polygon

## EXAMPLES:
### Adding a marker:
```
from sartopo_python import SartopoSession
import time
  
sts=SartopoSession("localhost:8080","<offlineMapID>")
fid=sts.addFolder("MyFolder")
sts.addMarker(39,-120,"stuff")
sts.addMarker(39.01,-120.01,"myStuff",folderId=fid)
r=sts.getFeatures("Marker")
print("r:"+str(r))
print("moving the marker after a pause:"+r[0]['id'])
time.sleep(5)
sts.addMarker(39.02,-120.02,r[0]['properties']['title'],existingId=r[0]['id'])
```
### Moving an existing marker:
```   
from sartopo_python import SartopoSession
import time

sts2=SartopoSession(
    "sartopo.com",
    "<onlineMapID>",
     configpath="../../sts.ini",
     account="<accountName>")
fid2=sts2.addFolder("MyOnlineFolder")
sts2.addMarker(39,-120,"onlineStuff")
sts2.addMarker(39.01,-119.99,"onlineStuff2",folderId=fid2)
r2=sts2.getFeatures("Marker")
print("return value from getFeatures('Marker'):")
print(json.dumps(r2,indent=3))
time.sleep(15)
print("moving online after a pause:"+r2[0]['id'])
sts2.addMarker(39.02,-119.98,r2[0]['properties']['title'],existingId=r2[0]['id'])
```
### Sync and callbacks:
```
from sartopo_python import SartopoSession

def pucb(*args):
    print("Property Updated: pucb called with args "+str(args))

def gucb(*args):
    print("Geometry Updated: gucb called with args "+str(args))

def nocb(*args):
    print("New Object: nocb called with args "+str(args))

def docb(*args):
    print("Deleted Object: docb called with args "+str(args))

sts=SartopoSession('sartopo.com','xxxx',
        configpath='../../sts.ini',
        account='account@gmail.com',
        syncDumpFile='../../xxxx.txt',
        propUpdateCallback=pucb,
        geometryUpdateCallback=gucb,
        newObjectCallback=nocb,
        deletedObjectCallback=docb)
```
### Geometry operations:
```
sts.cut('AC 103','b0')
sts.cut('a1','b1')
sts.cut('a8','b8',deleteCutter=False)

# argument is a feature
a10=sts.getFeatures(title='a10')[0]
b10=sts.getFeatures(title='b10')[0]
sts.cut(a10,b10)

# argument is id
a12=sts.getFeatures(title='a12')[0]
b12=sts.getFeatures(title='b12')[0]
sts.cut(a12['id'],b12['id'])

sts.crop('a14','b14')
sts.crop('a15','b15',beyond=0)
```

## Signed Requests
Requests to localhost do not require any authentication; requests to sartopo.com do require authentication in the form of request signatures.

If the sartopo session object was created with 'sartopo.com' as part of the URL, then this module will sign all requests before sending.

Authenticaion information required to generate the signed requests includes a request expiration timestamp (just a couple minutes in the future is fine), a public key, and an ID code.  For a good explanation of how to determine those three items, see the README at https://github.com/elliottshane/sme-sartopo-mapsrv.

Once those three items are determined, they should be stored in a configparser-compatible file that should look like the following:
```
# sartopo_python config file
# This file contains credentials used to send API map requests
#  to sartopo.com.  Protect and do not distribute these credentials.

[myaccount@gmail.com]
id=123456ABCDEF
key=aBcDeF12345somepublickey
expires=1234567890
```
An explanation of how the SartopoSession constructor arguments are used to determine credentials, if sartopo.com is in the URL:
```
   # if configpath and account are specified,
   #  conigpath must be the full pathname of a configparser-compliant
   #  config file, and account must be the name of a section within it,
   #  containing keys 'id', 'key', and 'expires'.
   # otherwise, those parameters must have been specified in this object's
   #  constructor.
   # if both are specified, first the config section is read and then
   #  any parameters of this object are used to override the config file
   #  values.
   # if any of those three values are still not specified, abort.
```

