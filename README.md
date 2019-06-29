# sartopo_python

Sartopo / Caltopo currently does not have a publically available API;
 this code calls the non-publicized API that could change at any time.

This module is intended to provide a simple, API-version-agnostic sartopo
 interface to other appliactions.

This python code is in no way supported or maintained by caltopo LLC
 or the authors of caltopo.com or sartopo.com.

## Installation:
```
pip install sartopo_python
```

## Provided functions in class SartopoSession:
### \_\_init\_\_ - create a new session
domainAndPort="localhost:8080"
mapID=None
### getFeatures - get a list of map features
featureClass=None - "Marker" etc to return only markers
since=0 - get features only since this timestamp
### addFolder - create a SARTopo folder
label="New Folder"
### addMarker - create a SARTopo marker
lat
lon
title="New Marker"
description=""
color="FF0000"
symbol="point"
rotation=None
folderId=None
(1.0.4) existingId="" - specify this to edit an existing marker
## Typical usage:

```
from sartopo_python import SartopoSession
sts=SartopoSession("localhost:8080","SBH")
fid=sts.addFolder("MyFolder")
sts.addMarker(39,-120,"stuff")
sts.addMarker(39,-121,"myStuff",folderId=fid)
r=sts.getFeatures("Marker")
print("sending with id:"+r[0][1])
sts.addMarker(39.2536,-121.0267,r[0][0],existingId=r[0][1])
```


