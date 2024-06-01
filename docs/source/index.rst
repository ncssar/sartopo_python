.. sartopo_python documentation master file, created by
   sphinx-quickstart on Fri May 17 19:27:57 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

:tocdepth: 1

sartopo_python
==========================================
CalTopo / SARTopo uses a web API, which is not currently documented or developed for general public use, and could change at any time.

This module provides a 'session' object which manages a data connection to a hosted map, and provides several wrapper methods and convenience methods that make calls to the non-publicized CalTopo API.

**This module is not written or maintained by CalTopo LLC or the authors of caltopo.com or sartopo.com.** See |caltopo_link| and |training_link|.

Categories of provided class methods:
   - account data access
   - feature creation
   - feature editing
   - feature querying
   - feature deletion
   - geometry operations


**NOTE: sartopo_python is changing names to caltopo_python.**
caltopo_python 1.0.x will be identical to sartopo_python 2.0.x.

sartopo_python will not receive any updates after 2.0.x.  That is, there will be no sartopo_python 2.1.0.
Patches / bug fixes to 1.0 / 2.0 will be applied to both packages, but,
minor and major version updates will only be applied to caltopo_python.

We suggest that you start incorporating these slight changes to your code now.

Key Features
===============

Internet or locally-hosted
--------------------------
In addition to the standard caltopo.com web interface, CalTopo provides a downloadable local HTTP server
called CalTopo Desktop (formerly CalTopo Offline or SARTopo Offline).  This module works with either solution.

Configuration file
------------------
User account details, including the authentication key, are kept on a local config file that you control.  A template configuration file
comes with this package.

Authentication
--------------
All HTTP requests sent by this package are signed in the format expected by CalTopo, using the authentication key from your
local configuration file.

Local cache
-----------
If the session is associated with a hosted map, this module will keep a local cache of the entire map data structure.  This reduces
the number of web requests needed, which reduces the time taken for most tasks.

Sync with callbacks
-------------------
To keep the local cache in sync with the hosted map, this module automatically requests and processes updates from the host at the specified sync interval.

This sync procedure is done in a background thread, so that it doesn't delay or interfere with your code.  Sync can be paused or disabled if needed.

You can also write callback functions that will be called whenever map data changes are found during sync.

Mapless session
---------------
You may want to initialize the session without specifying a map, e.g. if you need to start by checking the list of available maps.

You can open a 'mapless' session by simply omitting the mapID argument when you initialize the session.  In that case, you can
open a map later, within the same session, with .openMap().

Any of the 'account data access methods' will work in a mapless session.
Most of the other class methods require an open map, so will fail with an error message if called in a mapless session.

Fixed choices
-------------
- Feature class
   Shape, Marker, AppTrack, LiveTrack, Folder, MapMediaObject, OperationalPeriod, Assignment, Clue, Resource, SmsLocationRequest
     - NOTE: Polygons and Lines are both part of the 'Shape' feature class, but are differentiated by the 'Geometry type' of 'Polygon' vs. 'LineString'. 
- Assignment priority
   HIGH, MEDIUM, LOW
- Assignment POD (Responsive, Unresponsive, Clue)
   HIGH, MEDIUM, LOW
- Assignment status
   DRAFT, PREPARED, INPROGRESS, COMPLETED
- Assignment resource type
   GROUND, GROUND-1, GROUND-2, GROUND-3, DOG, DOG-TRAIL, DOG-AREA, DOG-HRD, OHV, BIKE, WATER, MOUNTED, AIR

Examples
========

Opening a session
-----------------

.. code-block:: python

   from sartopo_python import SartopoSession

   # open an online session and map
   sts=SartopoSession('caltopo.com','A1B2C',
         configpath='../../sts.ini',
         account='joe@domain.com')

   # open a CalTopo Desktop session and map
   sts=SartopoSession('localhost:8080','A1B2C',
         configpath='../../sts.ini',
         account='joe@domain.com')

   # open an online mapless session
   sts=SartopoSession('caltopo.com',
         configpath='../../sts.ini',
         account='joe@domain.com')

   # open a map, for a session that was initially mapless
   sts.openMap('A1B2C')

Syncing and callbacks
---------------------

.. code-block:: python

   def pucb(*args):
      print('Property Updated: pucb called with args '+str(args))

   def gucb(*args):
      print('Geometry Updated: gucb called with args '+str(args))

   def nocb(*args):
      print('New Object: nocb called with args '+str(args))

   def docb(*args):
      print('Deleted Object: docb called with args '+str(args))

   sts=SartopoSession('caltopo.com','A1B2C',
         configpath='../../sts.ini',
         account='joe@domain.com',
         propUpdateCallback=pucb,
         geometryUpdateCallback=gucb,
         newObjectCallback=nocb,
         deletedObjectCallback=docb)

Getting map data and account data
---------------------------------

.. code-block:: python

   # get the personal map list (for joe@domain.com)
   sts.getMapList()

   # get the MyTeam map list (assuming joe@domain.com is a member of MyTeam)
   sts.getMapList('MyTeam')

   # get a dict of all map lists (for joe@domain.com)
   sts.getAllMapLists()

   # get the title of a map
   sts.getMapTitle('A1B2C')

   # get the list of titles of group accounts of which joe@domain.com is a member
   sts.getGroupAccountTitles()

Adding features
---------------

.. code-block:: python

   # add a marker
   sts.addMarker(39,-120,'MyMarker')

   # add a folder
   fid=sts.addFolder('MyFolder')

   # add a marker in the folder
   myMarker2=sts.addMarker(39.01,-120.01,'MyMarker2',folderId=fid)
   
   # add a line
   sts.addLine([[39,-120],[39.1,-120.1]],'MyLine')

   # prepare to add a polygon - queue it for later
   sts.addPolygon([[39,-120],[39.1,-120.1],[39.1,-120]],'MyPolygon',queue=True)

   # add an Operational Period
   op1=sts.addOperationalPeriod('1')

   # prepare to add a line assignment - queue it for later
   aa=sts.addLineAssignment([[39.2,-120],[39.2,-120.1]],
         letter='AA',
         opId=op1,
         resourceType='DOG-TRAIL',
         description='FindEm',
         queue=True)

   sts.addAreaAssignment([[39.3,-120],[39.4,-120.1],[39.4,-120]],
         letter='AB',
         number='104',
         opId=op1,
         resourceType='DOG-AREA',
         description='FindEmFirst',
         responsivePOD='HIGH',
         priority='HIGH')

   # add the queued features now (MyPolygon and AA)
   sts.flush()

Querying and editing features
-----------------------------

.. code-block:: python

   myMarker=sts.getFeature('Marker','MyMarker')

   sts.editFeature(myMarker['id'],properties={'title','NewTitle'})

   sts.moveMarker(39,-121.5,myMarker['id'])

   sts.editMarkerDescription('New marker description',myMarker['id'])

Geometry operations
-------------------

.. code-block:: python

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

Deleting features
-----------------

.. code-block:: python

   sts.delFeature(aa)

   sts.delMarkers([myMarker,myMarker2])

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |caltopo_link| raw:: html

   <a href="https://caltopo.com" target="_blank">caltopo.com</a>

.. |training_link| raw:: html

   <a href="https://training.caltopo.com" target="_blank">training.caltopo.com</a>
