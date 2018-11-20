# sartopo_python

Sartopo / Caltopo currently does not have a publically available API;
 this code calls the non-publicized API that could change at any time.

This module is intended to provide a simple, API-version-agnostic sartopo
 interface to other appliactions.

This python code is in no way supported or maintained by caltopo LLC
 or the authors of caltopo.com or sartopo.com.

## Installation:
```
pip intall sartopo_python
```

## Provided functions in class SartopoSession:
### \_\_init\_\_ - create a new session
domainAndPort="localhost:8080"
mapID=None
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
## Typical usage:

```
from sartopo_python import SartopoSession

sts=SartopoSession(domainAndPort=domainAndPort,mapID=mapID)

fid=sts.addFolder("Buckshot")
sts.addMarker(lat,lon,title,description,color,symbol,None,fid)
```
