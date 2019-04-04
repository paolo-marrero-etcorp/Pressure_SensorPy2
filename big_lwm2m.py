'''
The Lwm2m module contains classes for defining lwm2m objects, instances and resources, and connecting to an lwm2m server.
'''

import wakaama_client_ext
import unittest
import types
import copy
import threading

STRING = wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_STRING
INT = wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_INTEGER
FLOAT = wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_FLOAT
BOOL = wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_BOOLEAN
OPAQUE = wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_OPAQUE
TIME = wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_INTEGER
NONE = wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_UNDEFINED

DATA_TYPES = (STRING, INT, FLOAT, BOOL, OPAQUE, TIME, NONE)
        
class Client(object):
    '''
    This class represents your lwm2m client. It is what will contain all of the lwm2m objects you define and 
    it contains the functionality for connecting to your lwm2m server.
    The Client class is instantiated an the Lwm2m module and is in a variable named lwm2m_client. The client is started by 
    calling the lwm2m_client.StartLwm2m function and passing in the name of the endpoint and a list of Lwm2m.Object instances.
    '''
    my_objects = {}

    def __new__(cls, *args, **kw):
        ''' Make this class a singleton.'''
        if not hasattr(cls, '_instance'):
            cls._instance = super(Client, cls).__new__(cls, *args, **kw)
        return cls._instance 

    def _register(self, objects):
        if isinstance(objects, Object):
            objects = [objects]

        for obj in objects:
            if not isinstance(obj, Object):
                raise TypeError("Only lwm2m.Object classes can be registered with lwm2m.Client.")            
            if self.my_objects.has_key(obj.id):
                raise KeyError("The object with id {} has already been registered.".format(obj.id))                
            for inst in obj:
                for res in inst:
                    if isinstance(res, DataResource):
                        res.object_id = obj.id
                        res.instance_id = inst.id
            self.my_objects[obj.id] = obj

    def get_resource(self, uri):
        ''' 
        Acquires a resource class instance using the lwm2m uri string of the form /object_id/instance_id/resource_id.
        For example to get the python resource class in lwm2m object 1000, instance 1, resource 3250 you would would pass
        the following string as a parameter 1000/1/3250
        
        **Args:**
        
        * uri: A string representing the lwm2m uri of a resource 
        '''
        uri = uri.strip("/")
        obj_id, inst_id, res_id = map(int, uri.split("/"))
        return self.my_objects[obj_id][inst_id][res_id]

    def __getitem__(self, object_id):
        '''
        Implements the index operator, returning the object with the given id.
        
        **Args:**
        
        * object_id: An integer value of the object id to retrieve
        
        **Returns:**
        
        A instance of type Lwm2m.Object
        
        **Exceptions:**
        
        * KeyError: Raised if there is no object with the given id in the client.
        '''
        try:
            return self.my_objects[object_id]
        except KeyError:
            raise KeyError("There is no object with id {}".format(object_id)) 
    
    def ResourceValChanged(self, object_id, instance_id, resource_id):
        """
        This function should be called when a resource value is changed externally to the Lwm2m code. For example,
        if you have a read resource which is periodically change on a seperate Thread you shoul call this function
        to inform the Lwm2m client that it has changed. 
        This is necessary because the server may request to Observe a resource, in which case the client should sends
        an update for the resource to tell the server when it has changed. The only way the client can tell if the
        resource has changed is if you tell it by calling this function
        
        **Args:**
        
        * object_id (int): The object that contains the resource
        * instance_id (int): The instance that contains the resource
        * resource_id (int): The changed resource
        """
        try:
            self._wakaama_client.ResourceValueChanged(object_id, instance_id, resource_id)
        except:
            # This function could be called by the user before the wakaama client is created. If so, then
            # we just ignore it.
            pass
    
    def StartLwm2m(self, endpoint_name, objects):
        ''' 
        Starts the lwm2m client. It will use the connection information in the security object to connect to the server.
        This function will run in the calling thread and will never return.
        '''
        self._register(objects)
        wakaama_objects = {object_id:obj.get_wakaama_object() for object_id, obj in self.my_objects.items()}
        self._wakaama_client = wakaama_client_ext.Lwm2mClientClass( wakaama_objects )
        self._wakaama_client.StartLwm2m(endpoint_name)
        
    def StartLwm2mThread(self, endpoint_name, objects):
        ''' 
        Starts the lwm2m client. It will use the connection information in the security object to connect to the server.
        This function will start a new thread and return.
        
        **Args:**
        
        * endpoint_name: A string that contains the name that will be used to connect to the server to identify this client
        
        * objects: An iterable containing instances of the Lwm2m.Object class that represent your client owns. After this is
                 called objects, instances and resource can no longer be registered. 
        '''        
        self._lwm2m_thread = threading.Thread(target=self.StartLwm2m, args = (endpoint_name, objects), name = "Lwm2mThread")
        self._lwm2m_thread.daemon = True
        self._lwm2m_thread.start()        

class ExecuteResource(object):
    """
    Inherit a subclass from this class to define a lwm2m execute resource. When the server sends an execute message with a resource
    id that corresponds to the resource id of this class, a callback function named "execute" will be called if you have defined one.
    """
    def __init__(self, resource_id):
        self.id = resource_id
        self._wakaama_type = NONE
        
    def _execute_callback(self, data):
        if callable(getattr(self, "execute", None)):
            return self.execute(data)
        return True
    
    
class DataResource(object):
    ''' DataResource is used as the base class for ReadResource, WriteResource, and ReadWriteResource. Should not be instantiated.'''
    def __new__(cls, *args, **kwargs):
        if cls is DataResource:
            raise TypeError("The DataResource class is not intended to be directly instantiated. Please use one of {}".format(base_classes))
        return object.__new__(cls, *args, **kwargs)
    
    def __init__(self, resource_id, data_type, init_val):
        '''
        .. note:: 
            You must ensure that this __init__ function gets called if you create a sub-class from this class.
        
        **Args:**
        
        * resource_id (int): The lwm2m resource id
        * data_type: One of STRING, INT, FLOAT, BOOL, or OPAQUE. These represent the lwm2m data types. The OPAQUE lwm2m data types
          is represented by a python bytearray.
        * init_val: The initial value to set self.value to. Must be a compatible type to data_type.'''
        self.object_id = None
        self.instance_id = None
        self.id = resource_id
        type_lookup = { STRING:str, INT:int, FLOAT:float, BOOL:bool, OPAQUE:bytearray, NONE:None}
        try:
            self._data_type = type_lookup[data_type]
        except:
            raise TypeError("The data_type parameter must be one of: {}".format(DATA_TYPES))
        self._wakaama_type = data_type
        self.__value = None
        self.value = init_val
          
    @property 
    def value(self):
        """
        Property that contains the current value of the resource. This attribute is automatically updated when read/write callbacks are called.
        This applies even to custom callbacks that are defined in a sub-class. 
        
        :getter: Returns the current value
        :setter: Set value and then informs the client if the it has changed. If the resource is being observed, the 
                 change notification will be sent to the server. 
                 
        .. note::
            If you wish to update the value of a resource outside of a callback function, you should set it using this function. If the resource 
            is being observed by the server, setting the value using this property will ensure that the server is notified if the value has
            changed.
        """    
        return self.__value
    
    @value.setter
    def value(self, set_val):
        try:
            set_val = self._data_type(set_val)
        except:
            raise TypeError("The value is not a compatible type to the lwm2m resource.") 
        if set_val != self.__value and self.instance_id and self.object_id:
            lwm2m_client.ResourceValChanged(self.object_id, self.instance_id, self.id)
        self.__value = set_val
      
class ReadResource(DataResource):
    """
    Represents a read only lwm2m resource. To use this class instiate and register it in an :py:class:`Lwm2m.Instance` class.
    This class defines a default read function which will return the default value set when the class is instantiated. You can 
    customize this resource by making a subclass and override the read function. The read function is a callback called when
    the server makes a read request on this resources id.
    """
    def _read_callback(self):
        if callable(getattr(self, "read", None)) and type(self) is not ReadResource:
            read_val = self.read()
            self.value = read_val
        return self.value
    
    def read(self):
        """
        A callback function called by the client when the server makes a read request. Customize this function by overriding it
        in a subclass. 
        
        **Returns:**
        
        A value of type set when this class was instantiated.
        """
        return self.value
    
class WriteResource(DataResource):
    def _write_callback(self, write_val):
        ret_val = True
        # Tests to see if the a subclass has defined a write function and calls the function
        # if it has.
        if callable(getattr(self, "write", None)) and type(self) is not WriteResource:
            ret_val = self.write(write_val)
        if ret_val:
            self.value = write_val
    
    def write(self, write_val):
        ''' A default implementation for the write function. Just sets the value. Should be overridden by subclass
        to provide custom functionality.
        arguments:
        write_val - The value to set. Should be a type that can be converted to the lwm2m type of the resource or a TypeError exception will be raised.'''
        self.value = write_val
            
class ReadWriteResource(ReadResource, WriteResource):
    pass
            
base_classes = (ExecuteResource, ReadResource, WriteResource, ReadWriteResource)            
            
class Object(object):
    """
    This class contains all of the instances, defined by the Lwm2m.Instance class. The :py:class:`Lwm2m.Instance` class will define all the resources that the object contains.
    The Object class is responsible for handling create and delete messages from the server.
    To customize the handling of these server messages you can write a class that inherits from this class, then define functions called "create" and "delete". 
    Both of these functions take one parameter of type int which is the instance Id to create/delete.
    
    The following simple example shows how to create a default Lwm2m.Object. A simple Lwm2m.Instance class is defined. For more information on this class please refer to 
    :py:class:`Instance`.

    .. code:: python
    
        # Defines a simple instance for this object.  
        class MyInstanceClass(Lwm2m.Instance):
            def __init__(self, instance_id):
                # Always call the init function for the parent class
                Lwm2m.Instance.__init__(self, instance_id)
                # Define your resources and register them with the parent class
                self.MyReadResource = Lwm2m.ReadResource(0, Lwm2m.INT, 123)
                self.register([self.MyReadResource])
        # Instantiate MyInstanceClass with id 0.
        MyInstance = MyInstanceClass(0)
        
        
        # Instantiate an Lwm2m.Object with id 0.
        MyObject = Lwm2m.Object(0)
        # Register your instance with your object
        MyObject.register([MyInstance)
    """
    def __init__(self, id, name="", default_instance_cls=None):
        """
        **Args:**
        
        * id (int): The lwm2m id of your object
        * name (string): An option name for your object
        * default_instance_cls (Lwm2m.Instance): When the server sends a message to create a new instance of this object this class, the instance will 
        be created with this default class. If the default_instance_cls parameter is not set then you will need to define a function called "create" to
        handle instance create calls from the server. 
        """
        self.id = id
        self._name = name
        self._default_instance_cls = default_instance_cls
        self._instances = {}

    def get_wakaama_object(self):
        wakaama_instances = {id:self._wakaama_resources(obj) for id, obj in self._instances.items()}
        return wakaama_client_ext.Lwm2mObjectClass( self.id, wakaama_instances, self.create_callback, self.delete_callback)

    def _wakaama_resources(self, instance):
        wakaama_resources = {}
        for resource_id, resource in instance._resources.items():
            wakaama_resources[resource_id] = wakaama_client_ext.Lwm2mResourceBaseClass( 
                resource_id,
                resource._wakaama_type, 
                getattr(resource, '_read_callback', None),
                getattr(resource, '_write_callback', None),
                getattr(resource, '_execute_callback', None))	
        return wakaama_resources

    def create_callback(self, instance_id):
        if self._instances.has_key(instance_id):
            return None
        # If there is a sub-class implementation of create, then call it
        if callable(getattr(self, "create", None)):
            new_instance = self.create(instance_id)
        else: 
            new_instance = self.create_default_instance(instance_id)
        if new_instance:
            try:
                # Try to register in case the user forgot to.
                self.register([new_instance])
            except:
                pass
            for res in new_instance:
                if isinstance(res, DataResource):
                    res.object_id = self.id
                    res.instance_id = instance_id                
            return self._wakaama_resources(new_instance)
        return None

    def create_default_instance(self, instance_id):
        """
        If you passed in the default instance default_instance_cls parametmer in the __init__ function of the Lwm2m.Object class, then 
        this function will instantiate that class and  return the instance created.
        
        **Args:**
        
        * instance_id (int): The id of the instance to instantiate.
        """
        if self._default_instance_cls:
            return self._default_instance_cls(instance_id)
        return None

    def delete_callback(self, id):
        # If there is a sub-class implementation of delete, then call it
        if callable(getattr(self, "delete", None)):
            self.delete(id)
        try:
            del(self._instances[id])
            return True
        except:
            return False

    def __iter__(self):
        """
        Returns an iterator for the instances in this class. This function makes this class an iterable, which allows you to use it in for loops
        """    
        return (inst for inst in self._instances.values())

    def __getitem__(self, id):
        '''
        Implements the index operator, returning the instance with the given id.
        
        **Args:**
        
        * id (int): An integer value of the instance id to retrieve
        
        **Returns:**
        
        A instance of type Lwm2m.Instance
        
        **Exceptions:**
        
        * KeyError: Raised if there is no instance with the given id in the object class.
        '''    
        try:
            return self._instances[id]
        except KeyError:
            raise KeyError("There is no instance with id {}".format(id)) 

    def register(self, instances):
        """
        Registers instances with the Lwm2m.Object class. This function must be called prior to using this class.
        
        **Args:**
        
        * instances: A list of :py:class:`Lwm2m.Instance` classes to register
        """
        for inst in instances:
            if not isinstance(inst, Instance):
                raise TypeError("Only lwm2m.Instance classes can be registered with lwm2m.Object.")
            if self._instances.has_key(inst.id):
                raise KeyError("The instance with id {} has already been registered.".format(inst.id))                
            self._instances[inst.id] = inst

class Instance(object):
    """
    The Lwm2m.Instance class holds all of the resources in your object. To define an object, make an instance class which inherits from this class.
    In your inherited class you'll define your resources. To define your resource you'll create instances of one of the resource classes: 
    :py:class:`ExecuteResource`, :py:class:`ReadResource`, :py:class:`WriteResource`, or :py:class:`ReadWriteResource`. When you've created instances of the
    resources, put them all in a list and call the :py:func:`register` function and pass the list as a paramemter.
    
    The following code demonstrates how you define an Lwm2m.Instance:
    
    .. code:: python
    
        class MyInstance(Lwm2m.Instance):
            READ_RESOURCE_ID = 1
            READ_WRITE_RESOURCE_ID = 2
            WRITE_RESOURCE_ID = 3
            
            def __init__(self, instance_id):
                # Always call the init function for the parent class
                Lwm2m.Instance.__init__(self, instance_id)
                
                # Define your resources
                self.MyReadResource = Lwm2m.ReadResource(self.READ_RESOURCE_ID, Lwm2m.INT, 123)
                self.MyReadWriteResource = Lwm2m.ReadWriteResource(self.READ_WRITE_RESOURCE_ID, Lwm2m.FLOAT, 30.0)
                self.MyWriteResource = Lwm2m.WriteResource(self.WRITE_RESOURCE_ID, Lwm2m.BOOL, False)
                
                # Register the resources with the parent class. The register function must be called or the 
                # parent Lwm2m.Instance class won't know about the resources and won't albe to perform 
                # server requests on these resources
                resources = [self.MyReadResource, self.MyReadWriteResource, self.MyWriteResource]
                self.register(resources)
    
    """
    
    def __init__(self, instance_id):
        """
        **Args:** 
        
        * instance_id (int): The integer id of this instance
        """
        self.id = instance_id
        self._resources = {}

    def register(self, resources):
        """
        Registers the resource classes with this instance. You should always call this function prior to using this class.
        
        **Args:**
        
        * resources: A list of one of the Lwm2m resource classes (:py:class:`ExecuteResource`, :py:class:`ReadResource`, :py:class:`WriteResource`, or :py:class:`ReadWriteResource`)
          to register in this instance.
        
        """
        for res in resources:
            if not isinstance(res, base_classes):
                raise TypeError("Cannot register resource. A resource must be an instance of, or inherit from the following classes: {}".format(base_classes))            
            if self._resources.has_key(res.id):
                raise KeyError("The resources with id {} has already been registered.".format(res.id))                 
            self._resources[res.id] = res

    def __getitem__(self, resource_id):
        '''
        Implements the index operator, returning the resource with the given id.
        
        **Args:**
        
        * resource_id: An integer value of the resource id of the class to retrieve
        
        **Returns:**
        
        A instance of type :py:class:`ExecuteResource`, :py:class:`ReadResource`, :py:class:`WriteResource`, or :py:class:`ReadWriteResource`
        
        **Exceptions:**
        
        * KeyError: Raised if there Instance doesn't have a resource with the given id.
        '''    
        try:
            return self._resources[resource_id]
        except KeyError:
            raise KeyError("There is no resource with id {}".format(resource_id)) 

    def __iter__(self):
        """
        Returns an iterator that iterates over the resource in this instance. 
        """
        return (res for res in self._resources.values())


# Create the client singleton
lwm2m_client = Client()

if __name__ == '__main__':
    class MyTest(unittest.TestCase):
        def test_execute_resource(self):
            class TestEx(ExecuteResource):
                def execute(self, data):
                    self.data = data
            
            ex_res = TestEx(1000)
    
            with self.assertRaises(AttributeError):
                ex_res.value
    
            self.assertEqual(1000, ex_res.id)
            self.assertEqual(NONE, ex_res._wakaama_type)
            ex_res.execute(100.0)
            self.assertEqual(100.0, ex_res.data)
    
    
        def build_url(self, id_vals):
            return "/".join( str(id_val) for id_val in id_vals )
                 
        def test_wakaama_read(self):
            TEST_OBJECT_ID = 1
            TEST_INSTANCE_ID = 1
            TEST_INT_RESOURCE_ID = 0
            TEST_STRING_RESOURCE_ID = 1
            TEST_BOOL_RESOURCE_ID = 2
            TEST_FLOAT_RESOURCE_ID = 3
            TEST_OPAQUE_RESOURCE_ID = 4   
            COAP_205_CONTENT = 69         
            class TestReadInstance(Instance):
                def __init__(self, inst_id):
                    Instance.__init__(self, inst_id)
                    test_write_resource = ReadWriteResource(TEST_INT_RESOURCE_ID, INT, 100)
                    test_string_resource = ReadWriteResource(TEST_STRING_RESOURCE_ID, STRING, "write_test_original")
                    test_bool_resource = ReadWriteResource(TEST_BOOL_RESOURCE_ID, BOOL, False)
                    test_float_resource = ReadWriteResource(TEST_FLOAT_RESOURCE_ID, FLOAT, 0.0)
                    test_opaque_resource = ReadWriteResource(TEST_OPAQUE_RESOURCE_ID, OPAQUE, bytearray(b'1234'))
                    resources = [test_write_resource, test_string_resource, test_bool_resource, test_float_resource, test_opaque_resource]
                    self.register(resources)
            TestReadObject = Object(TEST_OBJECT_ID, "TestReadObject", TestReadInstance)
            default_instance = TestReadObject.create_default_instance(TEST_INSTANCE_ID)
            TestReadObject.register([default_instance]) 
            wakaama_object = TestReadObject.get_wakaama_object()
            
            lwm2m_client._register([TestReadObject])
            
            read_vals = [TEST_INT_RESOURCE_ID, TEST_STRING_RESOURCE_ID, TEST_BOOL_RESOURCE_ID, TEST_FLOAT_RESOURCE_ID, TEST_OPAQUE_RESOURCE_ID]
            ret_val = wakaama_object.UnitTest_Read(TEST_INSTANCE_ID, read_vals)
            self.assertEqual(COAP_205_CONTENT, ret_val['result'])
            if COAP_205_CONTENT == ret_val['result']:
                self.assertEqual(ret_val['values'], [100, "write_test_original", False, 0.0, bytearray(b'1234')])
            
            INT_VAL = 200.0
            STR_VAL = "write_test_new"
            BOOL_VAL = True
            FLOAT_VAL = 100.0
            OPAQUE_VAL = bytearray(b'abcd')
            
            lwm2m_client.get_resource("1/1/0").value = INT_VAL
            lwm2m_client.get_resource("1/1/1").value = STR_VAL
            lwm2m_client.get_resource("1/1/2").value = BOOL_VAL
            lwm2m_client.get_resource("1/1/3").value = FLOAT_VAL
            lwm2m_client.get_resource("1/1/4").value = OPAQUE_VAL
            
            ret_val = wakaama_object.UnitTest_Read(TEST_INSTANCE_ID, read_vals)
            self.assertEqual(COAP_205_CONTENT, ret_val['result'])
            if COAP_205_CONTENT == ret_val['result']:
                self.assertEqual(ret_val['values'], [INT_VAL, STR_VAL, BOOL_VAL, FLOAT_VAL, OPAQUE_VAL])           
            
        def test_wakaama_create(self):
            TEST_OBJECT_ID = 3
            TEST_INSTANCE_ID = 1
            TEST_NEW_INSTANCE_ID = 2
            TEST_INT_RESOURCE_ID = 0
            TEST_STRING_RESOURCE_ID = 1
            TEST_BOOL_RESOURCE_ID = 2
            TEST_FLOAT_RESOURCE_ID = 3
            TEST_OPAQUE_RESOURCE_ID = 4
            COAP_201_CREATED = 65
            COAP_202_DELETED = 66
            TEST_INT_VAL = 200
            FLOAT_TEST_VAL = 150.5
            OPAQUE_TEST_VAL = bytearray(b'abcd')
            STRING_TEST_VAL = "write_test_updated"
            class TestWritInstance(Instance):
                def __init__(self, inst_id):
                    Instance.__init__(self, inst_id)
                    test_write_resource = ReadWriteResource(TEST_INT_RESOURCE_ID, INT, 100)
                    test_string_resource = ReadWriteResource(TEST_STRING_RESOURCE_ID, STRING, "write_test_original")
                    test_bool_resource = ReadWriteResource(TEST_BOOL_RESOURCE_ID, BOOL, False)
                    test_float_resource = ReadWriteResource(TEST_FLOAT_RESOURCE_ID, FLOAT, 0.0)
                    test_opaque_resource = ReadWriteResource(TEST_OPAQUE_RESOURCE_ID, OPAQUE, bytearray(b'1234'))
                    resources = [test_write_resource, test_string_resource, test_bool_resource, test_float_resource, test_opaque_resource]
                    self.register(resources)
                    
            TestWriteObject = Object(TEST_OBJECT_ID, "TestWriteObject", TestWritInstance)
            default_instance = TestWriteObject.create_default_instance(TEST_INSTANCE_ID)
            TestWriteObject.register([default_instance])
            
            lwm2m_client._register([TestWriteObject])
            wakaama_object = TestWriteObject.get_wakaama_object()
            
            write_vals = [ {"resource_id":TEST_INT_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_INTEGER, "write_value": TEST_INT_VAL},
                            {"resource_id":TEST_STRING_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_STRING, "write_value": STRING_TEST_VAL},
                            {"resource_id":TEST_BOOL_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_BOOLEAN, "write_value": True},
                            {"resource_id":TEST_FLOAT_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_FLOAT, "write_value": FLOAT_TEST_VAL},
                            {"resource_id":TEST_OPAQUE_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_OPAQUE, "write_value": OPAQUE_TEST_VAL}]
            
            self.assertEqual(COAP_201_CREATED, wakaama_object.UnitTest_Create(TEST_NEW_INSTANCE_ID, write_vals)) 
            self.assertEqual(lwm2m_client.get_resource("3/2/0").value, TEST_INT_VAL)
            self.assertEqual(lwm2m_client.get_resource("3/2/1").value, STRING_TEST_VAL)   
            self.assertEqual(lwm2m_client.get_resource("3/2/2").value, True)   
            self.assertEqual(lwm2m_client.get_resource("3/2/3").value, FLOAT_TEST_VAL)   
            self.assertEqual(lwm2m_client.get_resource("3/2/4").value, OPAQUE_TEST_VAL)   
            
            self.assertEqual(COAP_202_DELETED, wakaama_object.UnitTest_Delete(TEST_NEW_INSTANCE_ID)) 
            with self.assertRaises(KeyError):
                inst = lwm2m_client[TEST_OBJECT_ID][TEST_NEW_INSTANCE_ID]           
                    
        def test_wakaama_write(self):
            TEST_OBJECT_ID = 0
            TEST_INSTANCE_ID = 1
            TEST_INT_RESOURCE_ID = 0
            TEST_STRING_RESOURCE_ID = 1
            TEST_BOOL_RESOURCE_ID = 2
            TEST_FLOAT_RESOURCE_ID = 3
            TEST_OPAQUE_RESOURCE_ID = 4
            COAP_204_CHANGED = 68
            TEST_INT_VAL = 200
            FLOAT_TEST_VAL = 150.5
            OPAQUE_TEST_VAL = bytearray(b'abcd')
            STRING_TEST_VAL = "write_test_updated"
            class TestWritInstance(Instance):
                def __init__(self, inst_id):
                    Instance.__init__(self, inst_id)
                    test_write_resource = ReadWriteResource(TEST_INT_RESOURCE_ID, INT, 100)
                    test_string_resource = ReadWriteResource(TEST_STRING_RESOURCE_ID, STRING, "write_test_original")
                    test_bool_resource = ReadWriteResource(TEST_BOOL_RESOURCE_ID, BOOL, False)
                    test_float_resource = ReadWriteResource(TEST_FLOAT_RESOURCE_ID, FLOAT, 0.0)
                    test_opaque_resource = ReadWriteResource(TEST_OPAQUE_RESOURCE_ID, OPAQUE, bytearray(b'1234'))
                    resources = [test_write_resource, test_string_resource, test_bool_resource, test_float_resource, test_opaque_resource]
                    self.register(resources)
                    
            TestWriteObject = Object(TEST_OBJECT_ID, "TestWriteObject", TestWritInstance)
            default_instance = TestWriteObject.create_default_instance(TEST_INSTANCE_ID)
            TestWriteObject.register([default_instance])
            
            lwm2m_client._register([TestWriteObject])
            wakaama_object = TestWriteObject.get_wakaama_object()
            
            write_vals = [ {"resource_id":TEST_INT_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_INTEGER, "write_value": TEST_INT_VAL},
                            {"resource_id":TEST_STRING_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_STRING, "write_value": STRING_TEST_VAL},
                            {"resource_id":TEST_BOOL_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_BOOLEAN, "write_value": True},
                            {"resource_id":TEST_FLOAT_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_FLOAT, "write_value": FLOAT_TEST_VAL},
                            {"resource_id":TEST_OPAQUE_RESOURCE_ID, "data_type": wakaama_client_ext.Lwm2mDataType.LWM2M_TYPE_OPAQUE, "write_value": OPAQUE_TEST_VAL}]
            
            self.assertEqual(COAP_204_CHANGED, wakaama_object.UnitTest_Write(TEST_INSTANCE_ID, write_vals))
            self.assertEqual(lwm2m_client[TEST_OBJECT_ID][TEST_INSTANCE_ID][TEST_INT_RESOURCE_ID].value, TEST_INT_VAL)
            self.assertEqual(lwm2m_client.get_resource(self.build_url([TEST_OBJECT_ID,TEST_INSTANCE_ID,TEST_INT_RESOURCE_ID])).value, TEST_INT_VAL)
            
            self.assertEqual(lwm2m_client[TEST_OBJECT_ID][TEST_INSTANCE_ID][TEST_STRING_RESOURCE_ID].value, STRING_TEST_VAL)
            self.assertEqual(lwm2m_client.get_resource(self.build_url([TEST_OBJECT_ID,TEST_INSTANCE_ID,TEST_STRING_RESOURCE_ID])).value, STRING_TEST_VAL)
            
            self.assertEqual(lwm2m_client[TEST_OBJECT_ID][TEST_INSTANCE_ID][TEST_BOOL_RESOURCE_ID].value, True)
            self.assertEqual(lwm2m_client.get_resource(self.build_url([TEST_OBJECT_ID,TEST_INSTANCE_ID,TEST_BOOL_RESOURCE_ID])).value, True)
            
            self.assertEqual(lwm2m_client[TEST_OBJECT_ID][TEST_INSTANCE_ID][TEST_FLOAT_RESOURCE_ID].value, FLOAT_TEST_VAL)
            self.assertEqual(lwm2m_client.get_resource(self.build_url([TEST_OBJECT_ID,TEST_INSTANCE_ID,TEST_FLOAT_RESOURCE_ID])).value, FLOAT_TEST_VAL)
            
            self.assertEqual(lwm2m_client[TEST_OBJECT_ID][TEST_INSTANCE_ID][TEST_OPAQUE_RESOURCE_ID].value, OPAQUE_TEST_VAL)
            self.assertEqual(lwm2m_client.get_resource(self.build_url([TEST_OBJECT_ID,TEST_INSTANCE_ID,TEST_OPAQUE_RESOURCE_ID])).value, OPAQUE_TEST_VAL)
            
        def test_resource(self):
            
            resource_classes = [ReadWriteResource, WriteResource, ReadResource]
            
            for res_class in resource_classes:
                with self.assertRaises(TypeError):
                    res_class(0, INT, "X")
                           
                resource_obj = res_class(0, STRING, "default_string")
                
                self.assertEqual("default_string", resource_obj.value)     
                self.assertEqual(0, resource_obj.id)
                self.assertEqual(STRING, resource_obj._wakaama_type)
                
                if res_class is ReadWriteResource:
                    with self.assertRaises(AttributeError):
                        resource_obj.execute("")
                    resource_obj.write("read_write_val")
                    self.assertEqual("read_write_val", resource_obj.read())
                    resource_obj.write("default_string")
                
                if res_class is ReadResource:
                    with self.assertRaises(AttributeError):
                        resource_obj.write("")
                    with self.assertRaises(AttributeError):
                        resource_obj.execute("")  
                    self.assertEqual("default_string", resource_obj.read()) 
                                          
                if res_class is WriteResource:
                    with self.assertRaises(AttributeError):
                        resource_obj.read()
                    with self.assertRaises(AttributeError):
                        resource_obj.execute("")  
                    resource_obj.write("write_val")
                    self.assertEqual("write_val", resource_obj.value)
                    resource_obj.write("default_string")         

    unittest.main()
