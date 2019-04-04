"""

This module contains functionality to retrieve the information needed to communicate with the ETC lwm2m server. 
Use it to obtain the lwm2m host name, identity, secret key, and endpoint.   

"""
import http
import binascii

GET_LWM2M_SECURITY_INFO = 'GET_LWM2M_SECURITY_INFO'

class RetVals:
    '''
    Defines a set of integer constants for the values that can be returned by :py:func:`get_lwm2m_security_info`.
    Use these values to check the return value of :py:func:`get_lwm2m_security_info` to see if the operation was
    successful.
    '''
    SUCCESS = 0 #: Indicates function was successful
    COMMUNICATION_ERROR = 18 #: Indicates function was unable to communicate with api server
    INTERNAL_SOFTWARE_ERROR = 19 #: Indicates an unknown software error has occurred


def get_lwm2m_security_info():
    """
    This function will return the lwm2m host name, identity, secret key, and endpoint.
    
    **Returns**:
    
    A tuple of two entries :code:`(return_value, lwm2m_info)`
    
    * return_value: One of the integer values defined in :py:class:`RetVals`
    
    * lwm2m_info: A dictionary with the following format 
    
    .. code:: python    
    
        {'LWM2M_IDENTITY': bytearray, 
         'LWM2M_HOST_NAME': string, 
         'LWM2M_SECRET_KEY': bytearray, 
         'LWM2M_ENDPOINT': string}
         

    **Code Example:**
    
    .. code:: 
    
        return_value, lwm2m_info = lwm2m.get_lwm2m_security_info()
        
        if return_value == lwm2m.RetVals.SUCCESS:
            identity = lwm2m_info['LWM2M_IDENTITY']
            host_name = lwm2m_info['LWM2M_HOST_NAME']
            secret_key = lwm2m_info['LWM2M_SECRET_KEY']
            endpoint_name = lwm2m_info['LWM2M_ENDPOINT']
    """
    _, return_value, lwm2m_info = http.perform_get(GET_LWM2M_SECURITY_INFO)
    
    lwm2m_info["LWM2M_HOST_NAME"] = lwm2m_info["LWM2M_HOST_NAME"].encode("utf-8")
    lwm2m_info["LWM2M_ENDPOINT"] = lwm2m_info["LWM2M_ENDPOINT"].encode("utf-8")
    lwm2m_info["LWM2M_IDENTITY"] = bytearray(lwm2m_info["LWM2M_IDENTITY"].encode("utf-8"), 'utf8')
    lwm2m_info["LWM2M_SECRET_KEY"] = bytearray(binascii.a2b_hex(lwm2m_info["LWM2M_SECRET_KEY"].encode("utf-8")))
    return return_value, lwm2m_info


