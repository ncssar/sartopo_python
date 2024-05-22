sartopo\_python package
=======================

Submodules
----------

sartopo\_python.sartopo\_python module
--------------------------------------
.. see https://stackoverflow.com/a/48682589/3577105
.. currentmodule:: sartopo_python.sartopo_python

.. autoclass:: SartopoSession

   **Session setup methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: openMap
   .. automethod:: _setupSession
   .. automethod:: _sendUserdata

   **Account data access methods (may be called from a mapless session)**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: getAccountData
   .. automethod:: getMapList
   .. automethod:: getAllMapLists
   .. automethod:: getMapTitle
   .. automethod:: getGroupAccountTitles

   **Feature creation methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: addFolder
   .. automethod:: addMarker
   .. automethod:: addLine
   .. automethod:: addPolygon
   .. automethod:: addLineAssignment
   .. automethod:: addAreaAssignment
   .. automethod:: addAppTrack


   **Feature deletion methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: delFeature
   .. automethod:: delFeatures
   .. automethod:: delMarker
   .. automethod:: delMarkers

   **Feature query methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: getFeature
   .. automethod:: getFeatures
      
   **Feature editing methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
   
   .. automethod:: editFeature
   .. automethod:: moveMarker
   .. automethod:: editMarkerDescription
   .. automethod:: removeDuplicatePoints
   .. automethod:: removeSpurs

   **Geometry operation methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: cut
   .. automethod:: expand
   .. automethod:: crop
   .. automethod:: buffer2
   .. automethod:: intersection2
   .. automethod:: getBounds

   **Internal data management methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: _doSync
   .. automethod:: _refresh
   .. automethod:: __del__
   .. automethod:: _start
   .. automethod:: _stop
   .. automethod:: _pause
   .. automethod:: _resume
   .. automethod:: _syncLoop
   .. automethod:: _getToken
   .. automethod:: _sendRequest
   .. automethod:: _flush
   .. automethod:: _delAsync
   .. automethod:: _getUsedSuffixList
   .. automethod:: _getNextAvailableSuffix

   **Internal helper methods**
   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   .. automethod:: _caseMatch
   .. automethod:: _twoify
   .. automethod:: _fourify

   .. :members:
   .. :undoc-members:
   .. :show-inheritance:

Module contents
---------------

.. automodule:: sartopo_python
   :members:
   :undoc-members:
   :show-inheritance:
