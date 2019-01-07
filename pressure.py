#!/usr/bin/python
""" Example app for the Morpheus. 
    The main purpose of this example app is to demonstrate the use of the ETC Python Lwm2m Module and the ETC Api Client Module.
    This example will connect to an lwm2m server and register a Pressure Sensor Object. It demonstrates how to define resources, instances, 
    and objects use the Python lwm2m library and how to start the client.
    The ETC API module is used to interface with the hardware and acquire the lwm2m connection information. The app uses the API module to:
        * set the sensor power pin high
        * read from an analog input pin to get the voltage of a pressure sensor
        * Read the analog process data, which is then used to calculate the pressure value from the raw voltage
        * Acquire the lwm2m uri, public key, and private key

    Required Hardware:
    * Name: senpwr. This will be on the PWR output and is used to power the sensor
    * Name: ai1. This will read the pressure sensor output.
    
    The names senpwr and ai1 are setup at build time in the Morpheus App Builder program.
"""
import Lwm2m
from Lwm2m import lwm2m_client
from Lwm2m import ReadResource
from Lwm2m import WriteResource
from Lwm2m import ReadWriteResource
from Lwm2m import ExecuteResource
from Lwm2m import STRING
from Lwm2m import INT
from Lwm2m import FLOAT
from Lwm2m import OPAQUE
from Lwm2m import BOOL

# The ETC API module. Used to interface to hardware, retrieve analog process configuration values, and get lwm2m connection info.
from api_client import return_values
from api_client import analog
from api_client import digital
from api_client import lwm2m

import logging
import binascii
    
logger = logging.getLogger("pressure")   
ch = logging.StreamHandler() 
ch.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
logger.addHandler(ch)

#=========================================================#
def enable_sensor_power():
    """ Sets the output on the SENPWR output high."""
    sen = digital.SensorPower("senpwr")  
    sen.set()
    
def get_analog_process_config():
    """ Calls the read_analog_process_config API client function to retrieve the min/max values of the sensor voltage and corresponding PSI.
    These values are used to calculate the PSI from the voltage output. 
    Exceptions are returned if the read_analog_process_config function returns an error or if the returned value is cannot be parsed."""
    status, response, value = analog.read_analog_process_config()
    
    if status != return_values.OK or response != return_values.RESULT_SUCCESS:
        raise Exception("Failed to retrieve the analog process config information. Received status {} and return value {}.".format(status,response))
        
    try:
        max_volts = float(value["AI1"]["max_voltage"]) 
        min_volts = float(value["AI1"]["min_voltage"]) 
        min_sen = float(value["AI1"]["min_sensor"])    
        max_sen = float(value["AI1"]["max_sensor"])
    except KeyError:
         raise Exception("The analog process config message received from the api server is not in the expected format. Unable to proceed.")
     
    return max_volts, min_volts, max_sen, min_sen          
    
def read_lwm2m_info():
    """ Uses the get_lwm2m_security_info API function to get the endpoint URI, the secret key and the secret key used to connect to the lwm2m server."""
    status, response, secure = lwm2m.get_lwm2m_security_info()
    
    if status != return_values.OK or response != return_values.RESULT_SUCCESS:
        raise Exception("Failed to retrieve the lwm2m connection information. Received status {} and return value {}.".format(status,response))
    
    try:
        lwm2m_uri = "coaps://" + secure["LWM2M_HOST_NAME"].encode("utf-8") + ":5684"
        lwm2m_endpoint = secure["LWM2M_ENDPOINT"].encode("utf-8")
        lwm2m_identity = secure["LWM2M_IDENTITY"].encode("utf-8")
        lwm2m_security = secure["LWM2M_SECRET_KEY"].encode("utf-8")
    except KeyError:
        raise Exception("The lwm2m security info message received from the api server is not in the expected format. Unable to proceed.")
    
    return lwm2m_uri, lwm2m_endpoint, lwm2m_identity, lwm2m_security

class PressureSensor:
    """ A class to read the pressure sensor voltage from a analog input and interpolatte it to a PSI value."""
    def __init__(self):
        self.max_volts, self.min_volts, self.max_sen, self.min_sen = get_analog_process_config()
        self.ai1 = analog.AI("ai1")  

    def read_psi(self):
        ''' This function uses the equation y = mx+b to convert the voltage to a pressure value.'''
        x = float(self.ai1.read_milli_volts()) / 1000.0
        m = (self.max_sen - self.min_sen) / (self.max_volts - self.min_volts)
        b = self.min_sen - ((self.max_sen - self.min_sen)/(self.max_volts - self.min_volts))*self.min_volts
        y = m * x + b 
        logger.debug("read_psi called: x = {}, m = {}, b = {}, y = {}".format(x,m,b,y))
        # The return value is clamped between the min and max values of the sensor
        return min( self.max_sen, max(self.min_sen, y ))


class ServerInstance(Lwm2m.Instance):
    """ A class that represents an lwm2m Server object. This is a manadatory lwm2m object. The class must inherit from the lwm2m.Instance class."""
    # These are the resource ids 
    SHORT_ID = 0
    LIFETIME = 1
    MIN_PERIOD = 2
    MAX_PERIOD = 3
    DISABLE_ID = 4
    TIMEOUT_ID = 5
    STORING_ID = 6
    BINDING_ID = 7
    UPDATE_ID = 8 
    
    def __init__(self, instance_id):
        # The init function for the Lwm2m.Instance base class must always be called.
        Lwm2m.Instance.__init__(self, instance_id)
        
        resources = [
            ReadResource(self.SHORT_ID, INT, 123),
            ReadWriteResource(self.LIFETIME, INT, 30),
            ReadWriteResource(self.MIN_PERIOD, INT, 0),
            ReadWriteResource(self.MAX_PERIOD, INT, 0),
            ReadWriteResource(self.DISABLE_ID, INT, 0),
            ExecuteResource(self.TIMEOUT_ID),
            ReadWriteResource(self.STORING_ID, BOOL, False),
            ReadWriteResource(self.BINDING_ID, STRING, "U"),
            ExecuteResource(self.UPDATE_ID)
            ]
        # register must be called to inform the lwm2m.Instance of the resources it contains.
        self.register(resources)


class PressureValue(Lwm2m.ReadResource):   
    """ This class represents an lwm2m pressure value resource. The class must inherit from Lwm2m.ResourceBase in order to be used by the
    client. Since this a read resource, the class must provide a read callback function. The callback must have the name 'read' and return
    a value of type float since this is an Lwm2m.FLOAT resource. """
    def __init__(self, pressure_sensor, *arg):
        # The init function for the Lwm2m.ResourceBase base class must always be called.
        Lwm2m.ReadResource.__init__(self, *arg)
        self.pressure_sensor = pressure_sensor
        
    def read(self):
        """This function is used as a callback by the lwm2m client."""
        # One method of getting a resource is calling get_resource from the client instance. get_resource
        # takes the lwm2m uri string as a parameter. The uri is the object id, then the instance id, then
        # the resource id.
        max_resource = lwm2m_client.get_resource("3323/1/5602")
        # Resources can also be accessed using the index operator from the client instance.
        min_resource = lwm2m_client[3323][1][5601]
        
        pressure = self.pressure_sensor.read_psi()
        
        max_resource.value = max(max_resource.value, pressure)
        min_resource.value = min(min_resource.value, pressure)
        logger.debug("PressureValue read called: pressure = {}, max = {}, min = {}".format(pressure, max_resource.value, min_resource.value))
        return pressure

class Reset_min_max(ExecuteResource):
    """ This class represents an lwm2m min/max reset resource. The class must inherit from Lwm2m.ExecuteResource in order to be used by the
    client. Since this an execute resource, the class must provide an execute callback function. The callback must have the name 'execute', and 
    take one argument that contains any data sent from the server as part of the execute request. The function should return a boolean value
    that indicates the success of the operation."""
    def __init__(self, pressure_sensor, *arg):
        ExecuteResource.__init__(self, *arg)
        self.pressure_sensor = pressure_sensor
        
    def execute(self, data):
        pressure = self.pressure_sensor.read_psi()
        # An attribute named parent_instance is set by the instance that owns the resource when the
        # resource is registered. This gives a convenient way to access other resources of the same
        # instance.
        lwm2m_client[3323][1][5601].value = pressure
        lwm2m_client[3323][1][5602].value = pressure
        return True


class PressureObjectInstance(Lwm2m.Instance):
    # These are the resource ids
    MIN_PRESSURE = 5601
    MAX_PRESSURE = 5602
    MIN_PRESSURE_RANGE = 5603
    MAX_PRESSURE_RANGE = 5604
    RESET_VALUES = 5605
    LINE_PRESSURE = 5700
    SENSOR_UNITS = 5701
    CURRENT_CALIBRATION = 5821
    APPLICATION_TYPE = 5750
    
    def __init__(self, instance_id):
        # The init function for the Lwm2m.Instance base class must always be called.
        Lwm2m.Instance.__init__(self, instance_id)
        self.pressure_sensor = PressureSensor()
        pressure = self.pressure_sensor.read_psi()
        
        resources = [
            ReadResource(self.MIN_PRESSURE, FLOAT, pressure),
            ReadResource(self.MAX_PRESSURE, FLOAT, pressure),
            ReadResource(self.MIN_PRESSURE_RANGE, FLOAT, self.pressure_sensor.min_sen),
            ReadResource(self.MAX_PRESSURE_RANGE, FLOAT, self.pressure_sensor.max_sen),
        
            Reset_min_max(self.pressure_sensor, self.RESET_VALUES),
            PressureValue(self.pressure_sensor, self.LINE_PRESSURE, FLOAT, 0.0),
            ReadWriteResource(self.SENSOR_UNITS, STRING, "PSI"),
            ReadWriteResource(self.CURRENT_CALIBRATION, STRING, "Calibration 1"),
            ReadWriteResource(self.APPLICATION_TYPE, STRING, "Line Pressure")
            ]
        self.register(resources)
    

class SecurityInstance(Lwm2m.Instance):
    LWM2M_SECURITY_MODE_PRE_SHARED_KEY = 0
    LWM2M_SECURITY_MODE_RAW_PUBLIC_KEY = 1
    LWM2M_SECURITY_MODE_CERTIFICATE = 2
    LWM2M_SECURITY_MODE_NONE = 3
    
    # These are the resource Ids for the sercurity instance
    URI = 0
    BOOSTRAP = 1
    SECURITY_MODE = 2
    PUBLIC_KEY = 3
    SERVER_PUBLIC_KEY = 4
    SECRET_KEY = 5
    SMS_SECURITY_MOE = 6
    SMS_KEY_PARAM = 7
    SMS_SECRET_KEY = 8
    SMS_SERVER_ID = 9
    SHORT_SERVER_ID = 10
    HOLDOFF_ID = 11
    BOOTSRAP_TIMEOUT = 12
    
    def __init__(self, instance_id):
        # The init function for the Lwm2m.Instance base class must always be called.
        Lwm2m.Instance.__init__(self, instance_id)
        
        uri, _, public_key, secret_key = read_lwm2m_info()
        resources = [
            ReadWriteResource(self.URI, STRING, uri),
            ReadWriteResource(self.BOOSTRAP, BOOL, False),
            ReadWriteResource(self.SECURITY_MODE, INT, self.LWM2M_SECURITY_MODE_PRE_SHARED_KEY),
            ReadWriteResource(self.PUBLIC_KEY, OPAQUE, bytearray(public_key, 'utf8')),
            ReadWriteResource(self.SERVER_PUBLIC_KEY, OPAQUE, bytearray()),
            ReadWriteResource(self.SECRET_KEY, OPAQUE, bytearray(binascii.a2b_hex(secret_key))) ,
            ReadWriteResource(self.SMS_SECURITY_MOE, INT, 0),
            ReadWriteResource(self.SMS_KEY_PARAM, OPAQUE, bytearray()),
            ReadWriteResource(self.SMS_SECRET_KEY, OPAQUE, bytearray()),
            ReadWriteResource(self.SMS_SERVER_ID, INT, 0),
            ReadWriteResource(self.SHORT_SERVER_ID, INT, 123),
            ReadWriteResource(self.HOLDOFF_ID, INT, 10),
            ReadWriteResource(self.BOOTSRAP_TIMEOUT, INT, 0)        
            ]
        # The register function must be called to inform the instance what resources it contains
        self.register(resources)

    
class DeviceIntance(Lwm2m.Instance):
    
    MANUFACTURER = 0
    MODEL_NUMBER = 1
    SERIAL_NUMBER = 2
    FIRMWARE_VERSION = 3
    FACTORY_RESET = 5
    TIMEZONE = 15
    
    def __init__(self, instance_id):
        # The init of the Instance parent class should always be called.
        Lwm2m.Instance.__init__(self, instance_id)
        
        resources = [
            ReadResource(self.MANUFACTURER, STRING, "Open Mobile Alliance"),
            ReadResource(self.MODEL_NUMBER, STRING, "Lightweight M2M Client"),
            ReadResource(self.SERIAL_NUMBER, STRING, "345000123"),
            ReadResource(self.FIRMWARE_VERSION, STRING, "1.0"),
            ExecuteResource(self.FACTORY_RESET),
            ReadResource(self.TIMEZONE, STRING, "Mountain")
            ]
        # The register function must be called to inform the instance what resources it contains
        self.register(resources)        


def build_objects():
    ''' This function will create the lwm2m object classes that are part of our lwm2m client.
    The objects are created using the lwm2m.Object base class, and passing in an instance class that
    serves as the default instance class. The default instance class will be used to create and register
    a new instance when the create_default_instance function is called.
    The security, server, and device objects are mandatory objects in lwm2m.'''
    security_object = Lwm2m.Object(0, "Security", SecurityInstance)
    instance = security_object.create_default_instance(0)
    security_object.register([instance])
    
    server_object = Lwm2m.Object(1, "Server", ServerInstance)
    instance = server_object.create_default_instance(0)
    server_object.register([instance])
    
    device_object = Lwm2m.Object(3, "Device", DeviceIntance)
    instance = device_object.create_default_instance(0)
    device_object.register([instance])
    
    pressure_object = Lwm2m.Object(3323, "PressureObject", PressureObjectInstance)
    instance = pressure_object.create_default_instance(1)
    pressure_object.register([instance])
    
    return [security_object, server_object, device_object, pressure_object]       

if __name__ == "__main__":
    sen = digital.SensorPower("senpwr")  
    sen.set()

    # StartLwm2mThread takes the name of the endpoint and an iterable that contains all the objects in our system.
    _, endpoint, _, _ = read_lwm2m_info()
    lwm2m_client.StartLwm2mThread(endpoint, build_objects())        

    while True:
        value = raw_input("Press q to quit. ")
        if value == "q":
            break
