# -*- coding: utf-8 -*-
"""
Created on Sun Jul 30 17:53:14 2017

@author: Michael Oberhofer
"""

import socket
import logging
import datetime as dt
from enum import Enum
from struct import unpack
from time import sleep
from contextlib import contextmanager

log = logging.getLogger('oxygenscpi')

def is_minimum_version(version, min_version):
    """
    Performs a version check
    """
    if version[0] > min_version[0]:
        return True
    if version[0] < min_version[0]:
        return False
    return version[1] >= min_version[1]

class OxygenSCPI:
    """
    Oxygen SCPI control class
    """
    def __init__(self, ip_addr, tcp_port = 10001):
        self._ip_addr = ip_addr
        self._tcp_port = tcp_port
        self._CONN_NUM_TRY = 3
        self._CONN_TIMEOUT = 5
        self._CONN_MSG_DELAY = 0.05
        self._TCP_BLOCK_SIZE = 4096
        self._sock = None
        #self.connect()
        self._headersActive = True
        self.channelList = []
        self._scpi_version = (1,5)
        self._value_dimension = None
        self._value_format = self.NumberFormat.ASCII
        self.elogChannelList = []
        self.elogTimestamp = "OFF"
        self._localElogStartTime = dt.datetime.now()
        self.DataStream = OxygenScpiDataStream(self)
        self.ChannelProperties = OxygenChannelProperties(self)

    def connect(self):
        for numTry in range(1, self._CONN_NUM_TRY+1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
            #sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 0)
            sock.settimeout(self._CONN_TIMEOUT)
            try:
                sock.connect((self._ip_addr, self._tcp_port))
                self._sock = sock
                self.headersOff()
                self.getVersion()
                self._getTransferChannels(False)
                self._getElogChannels(False)
                self._getElogTimestamp()
                return True
            except ConnectionRefusedError as msg:
                template = "Connection to {!s}:{:d} refused: {!s}"
                log.error(template.format(self._ip_addr, self._tcp_port, msg))
                sock = None
                return False
            except OSError as msg:
                if numTry < self._CONN_NUM_TRY:
                    continue
                template = "Connection to {!s}:{:d} failed: {!s}"
                sock = None
                log.error(template.format(self._ip_addr, self._tcp_port, msg))
                return False
        self._sock = sock

    def disconnect(self):
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()
        except OSError as msg:
            log.error("Error Shutting Down: %s", msg)
        except AttributeError as msg:
            log.error("Error Shutting Down: %s", msg)
        self._sock = None

    def _sendRaw(self, cmd):
        cmd += '\n'
        if self._sock is None:
            self.connect()
        if self._sock is not None:
            try:
                self._sock.sendall(cmd.encode())
                sleep(self._CONN_MSG_DELAY)
                return True
            except OSError as msg:
                self.disconnect()
                template = "{!s}"
                log.error(template.format(msg))
        return False

    def _askRaw(self, cmd):
        cmd += '\n'
        if self._sock is None:
            self.connect()
        if self._sock is not None:
            try:
                self._sock.sendall(cmd.encode())
                answerMsg = bytes(0)
                while True:
                    data = self._sock.recv(self._TCP_BLOCK_SIZE)
                    answerMsg += data
                    if data[-1:] == b'\n':
                        return answerMsg
            except OSError as msg:
                self.disconnect()
                template = "{!s}"
                log.error(template.format(msg))
        return False

    def getIdn(self):
        ret = self._askRaw('*IDN?')
        if type(ret) == bytes:
            return ret.decode().strip()
        return False

    def getVersion(self):
        """
        SCPI,"1999.0",RC_SCPI,"1.6",OXYGEN,"2.5.71"
        """
        ret = self._askRaw('*VER?')
        if type(ret) == bytes:
            ret = ret.decode().strip().split(',')
            self._scpi_version = ret[3].replace('"','').split('.')
            self._scpi_version = (int(self._scpi_version[0]), int(self._scpi_version[1]))
            return self._scpi_version
        return None

    def reset(self):
        self._sendRaw('*RST')

    def headersOff(self):
        """
        Deactivate Headers on response
        """
        self._sendRaw(':COMM:HEAD OFF')
        self._headersActive = False

    def setRate(self, rate=500):
        """Sets the Aggregation Rate of the measurement device

        This Function sets the aggregation rate (mean value) to the
        specified value in milliseconds

        Args:
            rate (int): interval in milliseconds

        Returns:
            Nothing
        """
        return self._sendRaw(':RATE {:d}ms'.format(rate))

    def loadSetup(self, setup_name):
        """Loads the specified setup on the measurement device

        This Function loads the specified measurement setup (.dms) on
        the measurement device

        Args:
            setup_name (str): Name or absolute path of the .dms file

        Returns:
            Nothing
        """
        return self._sendRaw(':SETUP:LOAD "{:s}"'.format(setup_name))

    def _getTransferChannels(self, add_log=True):
        """Reads the channels to be transferred within the numeric system.

        This function reads the actual list of channels to be transferred within
        the numeric system and updates the attribute 'channelNames' with a list
        of strings containing the actual channel names. It is called at
        __init__ to get the previously set channels.

        Args:
            add_log (bool): Indicate in function should log or not.

        Returns:
            True if Suceeded, False if not
        """
        ret = self._askRaw(':NUM:NORMAL:ITEMS?')
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':NUM:ITEMS ','')
            channelNames = ret.split('","')
            channelNames = [chName.replace('"','') for chName in channelNames]
            if len(channelNames) == 1:
                if add_log:
                    log.debug('One Channel Set: {:s}'.format(channelNames[0]))
                if channelNames[0] == 'NONE':
                    channelNames = []
                    if add_log:
                        log.warning('No Channel Set')
            self.channelList = channelNames
            ret = self.setNumberChannels()
            if not ret:
                return False
            if is_minimum_version(self._scpi_version, (1,6)) and channelNames:
                return self.getValueDimensions()
            return True
        return False

    def setTransferChannels(self, channelNames, includeRelTime=False, includeAbsTime=False):
        """Sets the channels to be transfered within the numeric system

        This Function sets the channels to be transfered. This list must
        contain Oxygen channel names.

        Args:
            channelNames (list of str): List of channel names

        Returns:
            True if Suceeded, False if not
        """
        if includeRelTime:
            channelNames.insert(0, "REL-TIME")
        if includeAbsTime:
            channelNames.insert(0, "ABS-TIME")
        channelListStr = '"'+'","'.join(channelNames)+'"'
        self._sendRaw(':NUM:NORMAL:ITEMS {:s}'.format(channelListStr))
        # Read back actual set channel names
        return self._getTransferChannels()

    def setNumberChannels(self, number=None):
        if number is None:
            number = len(self.channelList)
        return self._sendRaw(':NUM:NORMAL:NUMBER {:d}'.format(number))

    class NumberFormat(Enum):
        ASCII = 0
        BINARY_INTEL = 1
        BINARY_MOTOROLA = 2

    def setNumberFormat(self, format=NumberFormat.ASCII):
        """
        Set the number format of the output
        Available since 1.20
        """
        if not is_minimum_version(self._scpi_version, (1,20)):
            raise NotImplementedError(":NUM:NORMAL:FORMAT requires protocol version 1.20")

        if format == self.NumberFormat.BINARY_INTEL:
            fmt = "BIN_INTEL"
        elif format == self.NumberFormat.BINARY_MOTOROLA:
            fmt = "BIN_MOTOROLA"
        else:
            fmt = "ASCII"

        self._sendRaw(':NUM:NORMAL:FORMAT {:s}'.format(fmt))
        self._value_format = format # Cache value

    def getNumberFormat(self) -> NumberFormat:
        """
        Read the number format of the output
        Available since 1.20
        """
        if not is_minimum_version(self._scpi_version, (1,20)):
            raise NotImplementedError(":NUM:NORMAL:FORMAT? requires protocol version 1.20")

        ret = self._askRaw(':NUM:NORM:FORMAT?')
        if isinstance(ret, bytes):
            format = ret.decode()
            if ' ' in format:
                format = format.split(' ')[1].rstrip()
            if format == "ASCII":
                return self.NumberFormat.ASCII
            if format == "BIN_INTEL":
                return self.NumberFormat.BINARY_INTEL
            if format == "BIN_MOTOROLA":
                return self.NumberFormat.BINARY_MOTOROLA
        raise Exception("Invalid NumberFormat")

    def getValueDimensions(self):
        """ Read the Dimension of the output
        Available since 1.6
        """
        # Asking for command ":NUM:NORM:DIMS?" times out when there are no
        # transfer channels selected.
        if self.channelList:
            ret = self._askRaw(':NUM:NORM:DIMS?')
            if isinstance(ret, bytes):
                dim = ret.decode()
                if ' ' in dim:
                    dim = dim.split(' ')[1]
                dim = dim.split(',')
                try:
                    self._value_dimension = [int(d) for d in dim]
                except TypeError:
                    self._value_dimension = False
                    return False
                return True
            return False
        return False

    def setValueMaxDimensions(self):
        if self.getValueDimensions():
            for idx in range(len(self._value_dimension)):
                self._sendRaw(':NUM:NORMAL:DIM{:d} MAX'.format(idx+1))
        else:
            return False
        return self.getValueDimensions()

    def _get_value_from_binary(self, data):
        """ Convert binary float32 values to float values array
        """
        numlenchars = int(chr(data[1]))
        array_length = int(data[2:(2+numlenchars)])
        data = data[(2 + numlenchars):(2 + numlenchars + array_length)]

        is_intel = self._value_format != self.NumberFormat.BINARY_MOTOROLA
        byteorder = "<" if is_intel else ">"
        return list(unpack(byteorder + "f" * (int(len(data)/4)), data))

    def _get_value_from_ascii(self, data):
        """ Convert ASCII values to array
        """
        data = data.decode().split(',')
        values = []
        for val in data:
            try:
                values.append(float(val))
                continue
            except ValueError:
                pass
            try:
                # Try to Parse DateTime "2017-10-10T12:16:52.33136+02:00"
                # Variable lenght of Sub-Seconds
                iso_ts = ''.join(val.replace('"','').rsplit(':', 1))
                timestamp = dt.datetime.strptime(iso_ts, '%Y-%m-%dT%H:%M:%S.%f%z')
                values.append(timestamp)
            except ValueError:
                values.append(val)
        return values

    def getValues(self):
        """Queries the actual values from the numeric system

        This Function queries the actual values from the channels defined in
        setTransferChannels.

        Args:
            None
        Returns:
            List of values (list)
        """
        try:
            data = self._askRaw(':NUM:NORM:VAL?')
        except OSError:
            return False

        if not type(data) is bytes:
            # No Data Available or Wrong Channel
            return False

        # Remove Header if Whitespace present
        if data.startswith(b':NUM:VAL '):
            data = data[9:]

        # Remove trailing newline
        if len(data) > 1 and data[-1] == ord('\n'):
            data = data[0:-1]

        # Check if we have binary data (e.g. #18abcdefgh)
        if len(data) > 2 and data[0] == ord('#'):
            data = self._get_value_from_binary(data)
        else:
            data = self._get_value_from_ascii(data)

        if self._value_dimension is not None:
            idx = 0
            values = []
            for dim in self._value_dimension:
                if dim <= 1:
                    # Add scalar value
                    values.append(data[idx])
                    idx += 1
                else:
                    # Add array value
                    values.append(data[idx:idx+dim])
                    idx += dim
            return values

        return data

    def storeSetFileName(self, file_name):
        """Sets the file name for the subsequent storing (recording) action

        This Function sets the file name for the subsequent storing action.
        The file will be stored in the default measurement folder on the device.

        Args:
            File Name (str)
        Returns:
            Status (bool)
        """
        try:
            return self._sendRaw(':STOR:FILE:NAME "{:s}"'.format(file_name))
        except OSError:
            return False

    def storeStart(self):
        """Starts the storing (recording) action or resumes if it was paused.

        This Function starts the storing action or resumes if it was paused
        The data will be stored in the file previous set with setStoreFileName.

        Args:
            None
        Returns:
            Status (bool)
        """
        try:
            return self._sendRaw(':STOR:START')
        except OSError:
            return False

    def storePause(self):
        """Pauses the storing (recording) action if it was started before.

        This Function pauses the storing action.

        Args:
            None
        Returns:
            Status (bool)
        """
        try:
            return self._sendRaw(':STOR:PAUSE')
        except OSError:
            return False

    def storeStop(self):
        """Stops the storing (recording) action if it was started before.

        This Function stops the storing action. The data file is now finished
        and can be used for analysis now.

        Args:
            None
        Returns:
            Status (bool)
        """
        try:
            return self._sendRaw(':STOR:STOP')
        except OSError:
            return False

    def getErrorSingle(self):
        """Query the first item in the error queue.

        This Function queries the first item in the error queue (oldest one)

        Args:
            None
        Returns:
            Error Message (str)
        """
        try:
            return self._askRaw(':SYST:ERR?')
        except OSError:
            return False

    def getErrorAll(self):
        try:
            return self._askRaw(':SYST:ERR:ALL?')
        except OSError:
            return None

    def lockScreen(self, lock_state=True):
        if lock_state:
            return self._sendRaw('SYST:KLOCK ON')
        return self._sendRaw('SYST:KLOCK OFF')

    def startAcquisition(self):
        try:
            return self._sendRaw(':ACQU:START')
        except OSError:
            return False

    def stopAcquisition(self):
        try:
            return self._sendRaw(':ACQU:STOP')
        except OSError:
            return False

    def restartAcquisition(self):
        try:
            return self._sendRaw(':ACQU:RESTART')
        except OSError:
            return False

    class AcquisitionState(Enum):
        STARTED = "Started"
        STOPPED = "Stopped"
        WAITING_FOR_SYNC = "Waiting_for_sync"

    def getAcquisitionState(self):
        ret = self._askRaw(':ACQU:STAT?')
        if isinstance(ret, bytes):
            state = ret.decode().strip()
            return self.AcquisitionState(state)

    def _getElogChannels(self, add_log=True):
        """Reads the channels to be transfered within the ELOG system.

        This function reads the actual list of channels to be transferred within
        the ELOG system and updates the attribute 'elogChannelList' with a list
        of strings containing the actual elog channel names. It is called at
        __init__ to get the previously set channels.

        Args:
            add_log (bool): Indicate in function should log or not.

        Returns:
            True if Suceeded, False if not
        """
        ret = self._askRaw(':ELOG:ITEMS?')
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':ELOG:ITEM ','')
            channel_names = ret.split('","')
            channel_names = [ch_name.replace('"','') for ch_name in channel_names]
            if len(channel_names) == 1:
                if add_log:
                    log.debug('One Channel Set: {:s}'.format(channel_names[0]))
                if channel_names[0] == 'NONE':
                    channel_names = []
                    if add_log:
                        log.warning('No Channel Set')
            self.elogChannelList = channel_names
            if len(channel_names) == 0:
                return False
            return True
        return False

    def setElogChannels(self, channel_names):
        """Sets the channels to be transfered within the ELOG system

        This Function sets the channels to be transfered. This list must
        contain Oxygen channel names.

        Args:
            channelNames (list of str): List of channel names

        Returns:
            True if Suceeded, False if not
        """
        if not is_minimum_version(self._scpi_version, (1,7)):
            log.warning('SCPI Version 1.7 or higher required')
            return False

        channel_list_str = '"'+'","'.join(channel_names)+'"'
        self._sendRaw(':ELOG:ITEMS {:s}'.format(channel_list_str))
        sleep(0.1)
        # Read back actual set channel names
        return self._getElogChannels()

    def startElog(self):
        self._localElogStartTime = dt.datetime.now()
        return self._sendRaw(':ELOG:START')

    def setElogPeriod(self, period):
        return self._sendRaw(':ELOG:PERIOD {:f}'.format(period))

    def stopElog(self):
        return self._sendRaw(':ELOG:STOP')

    @contextmanager
    def elogContext(self):
        """Safely starts and stops external logging.

        This function should be used in a with statement to start external
        logging and immediately stops it when either exiting the context
        or when an Exception occurs within the context.

        Example usage:
            with mDevice.startElog():
                # Here elog is started
                time.sleep(10)
                data = mDevice.fetchElog()
            # Here elog is stopped
        """
        try:
            self.startElog()
            yield
        finally:
            self.stopElog()

    def _getElogTimestamp(self):
        """Get external logging configured timestamp.

        Returns:
            External logging timestamp string obtained from ':ELOG:TIM?'
        """
        ret = self._askRaw(':ELOG:TIM?')
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            self.elogTimestamp = ret
            return ret
        return False

    def setElogTimestamp(self, tsType='REL'):
        if tsType in ('REL', 'ABS', 'ELOG'):
            self._sendRaw(f':ELOG:TIM {tsType}')
            ts_read = self._getElogTimestamp()
            return ts_read == tsType
        send_ok = self._sendRaw(':ELOG:TIM OFF')
        ts_read = self._getElogTimestamp()
        return send_ok

    def fetchElog(self, raw_string=True):
        data = self._askRaw(':ELOG:FETCH?')
        if type(data) is bytes:
            data = data.decode()
        else:
            return False
        if any(d in data for d in ('NONE', 'ERROR')):
            return False
        # Remove Header if Whitespace present
        if ' ' in data:
            data = data.split(' ')[1]
        data = data.split(',')
        num_ch = len(self.elogChannelList)
        if self.elogTimestamp in ('REL', 'ABS', 'ELOG'):
            num_ch += 1
        #print(len(data)/(1.0*num_ch), data)
        num_items = int(len(data)/num_ch)
        data = [data[i*num_ch:i*num_ch+num_ch] for i in range(num_items)]
        if not raw_string:
            for i, row in enumerate(data):
                data[i] = self._convertElogArray(row)
        return data

    def _convertElogArray(self, data_array):
        """Converts a single array from fetchElog string values into float.
        
        If the Elog timestamp is set to 'ABS' then the first value of the array
        is converted into datetime object.

        Args:
        data_array : list of strings
            List containing single array of string measurements from fetchElog.

        Returns:
            List with value types converted to float (datetime for value at
            index 0 if timestamp is ABS).
        """
        # When ELOG timestamp is set to ABS, the first value of a row is a
        # datetime string and the remaining values are strings that can
        # be converted to floating point numbers.
        if self.elogTimestamp == "ABS":
            new_array = []
            dtime = data_array[0].replace('"', '')
            # Oxygen's datetime with whole seconds does not display microseconds
            # for those cases the ".%f" formatting is excluded.
            fmt = '%Y-%m-%dT%H:%M:%S.%f' if '.' in dtime else '%Y-%m-%dT%H:%M:%S'
            new_array.append(dt.datetime.strptime(dtime, fmt))
            new_array.extend(float(value) for value in data_array[1:])
        else:
            new_array = [float(value) for value in data_array]
        return new_array

    def fetchElogAccumulated(self, timeout=10):
        """Fetch ELOG until the actual timestamp is reached.

        This function blocks the execution and keeps fetching elog values until
        a fetched timestamp is higher than the timestamp saved at the moment in
        which the function was called. If called right after starting the
        external logging, it is possible that the function needs longer because
        the update of the Dewetron's buffer is not instantaneous.

        Depending on the internet connection, the function itself can take a few
        seconds to be excecuted.
        
        It requires the elog timestamp to be either 'ABS' or 'ELOG'.
        - With 'ABS' timestamp, the stop condition will compare the absolute
        timestamp from the system executing the function with the timestamp from
        the operating system in which Oxygen is running.
        - With 'ELOG' timestamp, the stop condition will be met when the fetched
        timestamp added to the timestamp in which the startElog function was
        called (tracked by _localElogStartTime) attribute is higher than the
        timestamp from execution of the function.

        Args:
            timeout (float): timeout for the accumulated fetching in seconds.

        Returns:
            List of lists (matrix like) containing the accumulated fetched values
            converted to float (datetime for values at first column if timestamp
            is ABS.)
        """

        call_tstamp = dt.datetime.now()

        def stopCondition(tstamp):
            """Checks if the measured timestamp has reached the call timestamp.
            """
            # Case for ELOG timestamp
            if self.elogTimestamp == "ELOG":
                tstamp = float(tstamp)
                return self._localElogStartTime + dt.timedelta(seconds=tstamp) >= call_tstamp
            # Case for ABS timestmap
            tstamp = tstamp.replace('"','')
            tstamp = dt.datetime.strptime(tstamp, '%Y-%m-%dT%H:%M:%S.%f')
            return tstamp >= call_tstamp

        # This function works only for ELOG and ABS timestamps
        if self.elogTimestamp in ("ELOG", "ABS"):
            combined_fetch = []
            while dt.datetime.now() - call_tstamp < dt.timedelta(seconds=timeout):
                data = self.fetchElog()
                # Keep fetching until data is received
                if not data:
                    sleep(0.05)
                    continue
                combined_fetch.extend(data)
                # Check if last fetched value reaches the call timestamp.
                if stopCondition(combined_fetch[-1][0]):
                    for i, row in enumerate(combined_fetch):
                        combined_fetch[i] = self._convertElogArray(row)
                    return combined_fetch
        return False

    def addMarker(self, label, description=None, time=None):
        if description is None and time is None:
            return self._sendRaw(':MARK:ADD "{:s}"'.format(label))
        if description is None:
            return self._sendRaw(':MARK:ADD "{:s}",{:f}'.format(label, time))
        if time is None:
            return self._sendRaw(':MARK:ADD "{:s}","{:s}"'.format(label, description))
        return self._sendRaw(':MARK:ADD "{:s}","{:s}",{:f}'.format(label, description, time))

    def getChannelList(self):
        ret = self._askRaw(':CHANNEL:NAMES?')
        if ret:
            ch_str_list = ret.decode().strip()
            ch_list = [item.replace('(','').replace(')','').replace('"','').split(',') for item in ch_str_list.split('),(')]
            return ch_list
        return None

    def getChannelListDict(self, key="ChannelName"):
        ch_list = self.getChannelList()
        if ch_list:
            ch_dict = {}
            for ch in ch_list:
                if key == "ChannelName":
                    if ch[1] in ch_dict:
                        print("Warning: Channel duplicate detected!")
                    ch_dict[ch[1]] = ch[0]
                else:
                    ch_dict[ch[0]] = ch[1]
            return ch_dict

        return None

    def getChannelPropValue(self, channel_id, prop):
        if type(channel_id) == int:
            channel_id = str(channel_id)
        ret = self._askRaw(f':CHANNEL:PROP? "{channel_id:s}","{prop:s}"')
        if ret:
            return ret.decode().strip()
        return None

    def getChannelPropNames(self, channel_id):
        if type(channel_id) == int:
            channel_id = str(channel_id)
        ret = self._askRaw(f':CHANNEL:ITEM{channel_id:s}:ATTR:NAMES?')
        if ret:
            return ret.decode().strip().replace('"','').split(",")
        return None

    def setChannelPropValue(self, channel_id, prop, val):
        if type(channel_id) == int:
            channel_id = str(channel_id)
        self._sendRaw(f':CHANNEL:PROP "{channel_id:s}","{prop:s}","{val:s}"')

# TODO: Better add and remove data stream instances
class OxygenScpiDataStream:
    def __init__(self, oxygen):
        self.oxygen = oxygen

    def setItems(self, channelNames, streamGroup=1):
        """ Set Datastream Items to be transfered
        """
        if not is_minimum_version(self.oxygen._scpi_version, (1,7)):
            log.warn('SCPI Version 1.7 or higher required')
            return False
        channelListStr = '"'+'","'.join(channelNames)+'"'
        ret = self.oxygen._sendRaw(':DST:ITEM{:d} {:s}'.format(streamGroup, channelListStr))
        sleep(0.1)
        # Read back actual set channel names
        ret = self.oxygen._askRaw(':DST:ITEM{:d}?'.format(streamGroup))
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':DST:ITEM{:d} '.format(streamGroup),'')
            channelNames = ret.split('","')
            channelNames = [chName.replace('"','') for chName in channelNames]
            if len(channelNames) == 1:
                log.debug('One Channel Set: {:s}'.format(channelNames[0]))
                if channelNames[0] == 'NONE':
                    channelNames = []
                    log.warn('No Channel Set')
            self.ChannelList = channelNames
            if len(channelNames) == 0:
                return False

            return True

        return False

    def setTcpPort(self, tcp_port, streamGroup=1):
        self.oxygen._sendRaw(':DST:PORT{:d} {:d}'.format(streamGroup, tcp_port))
        return True

    def init(self, streamGroup=1):
        if streamGroup == 'all':
            self.oxygen._sendRaw(':DST:INIT {:s}'.format(streamGroup))
        elif type(streamGroup) == int:
            self.oxygen._sendRaw(':DST:INIT {:d}'.format(streamGroup))
        else:
            return False
        return True

    def start(self, streamGroup=1):
        if streamGroup == 'all':
            self.oxygen._sendRaw(':DST:START ALL')
        elif type(streamGroup) == int:
            self.oxygen._sendRaw(':DST:START {:d}'.format(streamGroup))
        else:
            return False
        return True

    def stop(self, streamGroup=1):
        if streamGroup == 'all':
            self.oxygen._sendRaw(':DST:STOP ALL')
        elif type(streamGroup) == int:
            self.oxygen._sendRaw(':DST:STOP {:d}'.format(streamGroup))
        else:
            return False
        return True

    def getState(self, streamGroup=1):
        ret = self.oxygen._askRaw(':DST:STAT{:d}?'.format(streamGroup))
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':DST:STAT ','')
            return ret
        return False

    def setTriggered(self, streamGroup=1, value=True):
        if value:
            self.oxygen._sendRaw(':DST:TRIG{:d} ON'.format(streamGroup))
        else:
            self.oxygen._sendRaw(':DST:TRIG{:d} OFF'.format(streamGroup))

    def reset(self):
        self.oxygen._sendRaw(':DST:RESET')

class OxygenChannelProperties:
    class OutputMode(Enum):
        FUNCTION_GENERATOR = "FunctionGenerator"
        CONSTANT = "ConstOutput"

    class Waveform(Enum):
        SINE = "Sine"
        SQUARE = "Square"
        TRIANGLE = "Triangle"

    def __init__(self, oxygen):
        self.oxygen = oxygen

    def getChannelType(self, ch_id):
        return self.oxygen.getChannelPropValue(ch_id, 'ChannelType').split(',')[2].replace(')','').replace('"','')

    def getChannelSamplerate(self, ch_id):
        try:
            return float(self.oxygen.getChannelPropValue(ch_id, 'SampleRate').split(',')[1].replace(')',''))
        except:
            return None

    def getTrionSlotNumber(self, ch_id):
        try:
            return int(self.oxygen.getChannelPropValue(ch_id, 'ID:TRION/SlotNumber').split(',')[1].replace(')',''))
        except:
            return None

    def getTrionBoardId(self, ch_id):
        try:
            return int(self.oxygen.getChannelPropValue(ch_id, 'ID:TRION/BoardId').split(',')[1].replace(')',''))
        except:
            return None

    def getTrionChannelIndex(self, ch_id):
        try:
            return int(self.oxygen.getChannelPropValue(ch_id, 'ID:TRION/ChannelIndex').split(',')[1].replace(')',''))
        except:
            return None

    def getChannelDomainName(self, ch_id):
        try:
            return self.oxygen.getChannelPropValue(ch_id, 'Neon/DomainUrl').split(',')[1].replace(')','').strip('"')
        except:
            return ""

    def getChannelLPFilterFreq(self, ch_id):
        """
        Possible Values for ret:
        - NONE
        - (SCALAR,20000.0,"Hz")
        - (STRING,"Auto")
        - (STRING,"Off")
        """
        try:
            ret = self.oxygen.getChannelPropValue(ch_id, 'LP_Filter_Freq')
            if ret == "NONE":
                return None
            ret_parts = ret.replace("(","").replace(")","").split(",")
            if ret_parts[0] == "STRING":
                return ret_parts[1].replace('"',"")
            if ret_parts[0] == "SCALAR":
                return float(ret_parts[1])
        except:
            pass
        return None

    def getChannelUsed(self, ch_id):
        ret = self.oxygen.getChannelPropValue(ch_id, 'Used').split(',')[1].strip(')"')
        if ret == "OFF":
            return False
        return True

    def getChannelRange(self, ch_id):
        try:
            ret = float(self.oxygen.getChannelPropValue(ch_id, 'Range').split(',')[3].strip(')"'))
        except:
            ret = None
        return ret

    def getTrionInputMode(self, ch_id):
        try:
            return self.oxygen.getChannelPropValue(ch_id, 'Mode')
        except:
            return ""

    def setTrionInputMode(self, ch_id, input_mode):
        self.oxygen.setChannelPropValue(ch_id, 'Mode', input_mode)

    def setTrionInputType(self, ch_id, input_type):
        self.oxygen.setChannelPropValue(ch_id, 'InputType', input_type)

    def setTrionOutputMode(self, ch_id, output_mode: OutputMode):
        self.oxygen.setChannelPropValue(ch_id, "Mode", output_mode.value)

    def getTrionLpFilterDelay(self, ch_id):
        try:
            ret = self.oxygen.getChannelPropValue(ch_id, 'LP_Filter_Delay')
            print(ret)
            ret = float(ret.split(',')[1].strip(')"'))/1e9 # Return in s instead of ns
        except:
            ret = 0.0
        return ret

    def setTrionOutputFgenAmplitude(self, ch_id, amplitude, unit="V", amplitude_type="RMS"):
        self.oxygen.setChannelPropValue(ch_id, "AmplitudeValue", amplitude_type)
        self.oxygen.setChannelPropValue(ch_id, "TRION/Amplitude", f"{amplitude:f} {unit:s}")

    def setTrionOutputFgenOffset(self, ch_id, offset, unit: str="V"):
        self.oxygen.setChannelPropValue(ch_id, "TRION/Offset", f"{offset:f} {unit:s}")

    def setTrionOutputFgenFrequency(self, ch_id, frequency):
        self.oxygen.setChannelPropValue(ch_id, "TRION/Frequency", f"{frequency:f} Hz")

    def setTrionOutputResolution(self, ch_id, resolution: str):
        """
        resolution, str, 'HighSpeed' or 'HighResolution'
        """
        self.oxygen.setChannelPropValue(ch_id, "TRION/OutputMode", resolution)

    def setTrionOutputConstant(self, ch_id, amplitude, unit="V", const_idx=0):
        #measurementDevice.setChannelPropValue(ch_props["AO 7/1"]['id'], "Mode", "ConstOutput")
        self.oxygen.setChannelPropValue(ch_id, f"TRION/SourceChannel_A_CONST/Const{const_idx:d}", f"{amplitude:f} {unit:s}")

    def setTrionOutputFgenWaveform(self, ch_id, waveform: Waveform):
        self.oxygen.setChannelPropValue(ch_id, "TRION/WaveForm", waveform.value)
