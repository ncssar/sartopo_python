.. sartopo_python documentation master file, created by
   sphinx-quickstart on Fri May 17 19:27:57 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

sartopo_python
==========================================
CalTopo / SARTopo uses a web API, which is not currently documented or developed for general public use, and could change at any time.

This module provides a 'session' object which manages a data connection to a hosted map, and provides several wrapper methods and convenience methods that make calls to the non-publicized CalTopo API.

Categories of provided class methods:
   - account data access
   - feature creation
   - feature editing
   - feature querying
   - feature deletion
   - geometry operations

The python code in this module is not written or maintained by CalTopo LLC or the authors of caltopo.com or sartopo.com.

**NOTE: sartopo_python is changing names to caltopo_python.**
caltopo_python 1.0.x will be identical to sartopo_python 2.0.x.

sartopo_python will not receive any updates after 2.0.x.  That is, patches / bug fixes to 1.0 / 2.0 will be applied to both packages, but,
minor and major version updates will only be applied to caltopo_python: there will be no sartopo_python 2.1.0.

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
the number of web requests needed, and the time taken for most tasks.

Sync
----
To keep the local cache in sync with the hosted map, this module automatically requests and processes updates from the host every few seconds.  This sync procedure
is done in a background thread, so that it doesn't delay or interfere with your code.  Sync can be paused or disabled if needed, and the sync interval can be specified.

Mapless session
---------------
You may want to initialize the session without specifying a map, e.g. if you need to start by checking the list of available maps.
You can open a 'mapless' session by simply omitting the mapID argument when you initialize the session.  In that case, you can
open a map later, within the same session, with .openMap().

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

.. toctree::
   :maxdepth: 2
   :caption: Contents:



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
