# Python Pressure Sensor App

A Morpheus Pressure Sensor App written in Python.

## Steps to Build

1. Clone Repo
2. Open Pressure_Sensor
2. Open Morpheus App Builder
3. In the "Build" Tab, click on "Load configuration". You will want to open app_builder_config.cfg. Your Morpheus App Builder Screen should appear similiar to this.
![Build Configuration](PressureSensorPy/resources/config_view.JPG)
4. Change Source Folder to the folder where this project has been cloned.
5. Click the "Build Code" button and wait a few minutes for everything to install. NOTE: It may appear to be frozen around 80% during the make command, just be patient and wait for it to load.
6.  Switch to the "Apps" Tab and select "pressure-sensor-py". Select an App-Token of your choice on the right-hand side and click "Run Executable"
7. After the app is installed, refresh the app list, and it should be visible. You will want to right-click the app, and click "Connect to App". This gives you access to the command-line where your app is being ran.
8. To view LWM2M results, go portal.etcvision.io, under devices, select the installed application, and click on the LWM2M Tab.


