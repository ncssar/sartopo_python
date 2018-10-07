# sartopo_python
Python calls for the caltopo / sartopo API

Initially, this is just a module and not a package, so, just place this file directly in your module search path (not in a subdirectory).

In the first half of 2018, the caltopo / sartopo http-request-based API changed.  This requires a rewrite of various python applications that call the API.

This was a good motivation to finally create a separate python project to interact with caltopo / sartopo.  The calls in this project are version-agnostic: the process of openening a session automatically determines the appropriate API version, so that the end application which calls the functions in this project does not need to know which API version is running.
