Fixed choices
-------------
For some property and argument values that are specified as strings, only certain values will be processed correctly.

These fixed lists of choices are determined by caltopo.com - not by the authors of this module.  The lists below are (hopefully) accurate at the time of writing, but, could change at any time.

The best option is to inspect outgoing network traffic while creating or editing a feature from the web interface with the selection you want.

- Marker symbol name
   There are well over a hundred available marker symbols.  Only a few common ones are listed here.  Use the technique above to find the one you want.

   point, c:ring, c:target1, cp, heatsource, clue

- Line pattern
   These formatted strings are too detailed to list here.  Use the technique above to find the one you want.

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

   GROUND, GROUND_1, GROUND_2, GROUND_3, DOG, DOG_TRAIL, DOG_AREA, DOG_HRD, OHV, BIKE, WATER, MOUNTED, AIR
   
     - NOTE: Underscores are used in the actual property values, but the web interface will display hyphens instead of underscores.