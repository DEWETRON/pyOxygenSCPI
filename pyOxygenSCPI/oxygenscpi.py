# -*- coding: utf-8 -*-
"""
Created on Sun Jul 30 17:53:14 2017

@author: Michael Oberhofer
"""

import socket
import logging
import datetime as dt
from enum import Enum
from time import sleep

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
        self._CONN_TIMEOUT = 2
        self._CONN_MSG_DELAY = 0.5
        self._TCP_BLOCK_SIZE = 4096
        self._sock = None
        #self.connect()
        self._headersActive = True
        self.channelList = []
        self._scpi_version = (1,5)
        self._value_dimension = None
        self.elogChannelList = []
        self.DataStream = OxygenScpiDataStream(self)

    def connect(self):
        for numTry in range(1, self._CONN_NUM_TRY+1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
            #sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 0)
            sock.settimeout(self._CONN_TIMEOUT)
            try:
                sock.connect((self._ip_addr, self._tcp_port))
                self._sock = sock
                self.getVersion()
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
        #if sock is not None:
        self._sock = sock
        #return False

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
                # TODO: Use EOL Character to detect End of Message
                while True:
                    data = self._sock.recv(self._TCP_BLOCK_SIZE)
                    if len(data) < self._TCP_BLOCK_SIZE:
                        answerMsg += data
                        return answerMsg
                    answerMsg += data
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
            ret = ret.decode().strip().split(' ')
            if len(ret)>1:
                ret = ''.join(ret[1:])
                ret = ret.split(',')
            else:
                ret = ret[0].split(',')
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
        ret = self._sendRaw(':NUM:NORMAL:ITEMS {:s}'.format(channelListStr))
        # Read back actual set channel names
        ret = self._askRaw(':NUM:NORMAL:ITEMS?')
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':NUM:ITEMS ','')
            channelNames = ret.split('","')
            channelNames = [chName.replace('"','') for chName in channelNames]
            if len(channelNames) == 1:
                log.debug('One Channel Set: {:s}'.format(channelNames[0]))
                if channelNames[0] == 'NONE':
                    channelNames = []
                    log.warning('No Channel Set')
            self.channelList = channelNames
            ret = self.setNumberChannels()
            if not ret:
                return False
            if is_minimum_version(self._scpi_version, (1,6)):
                return self.getValueDimensions()
            return True
        return False

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
            raise NotImplementedError(":NUM:NORMAL:FORMAT requires protocol version 1.20");

        if format == self.NumberFormat.BINARY_INTEL:
            fmt = "BIN_INTEL"
        elif format == self.NumberFormat.BINARY_MOTOROLA:
            fmt = "BIN_MOTOROLA"
        else:
            fmt = "ASCII"

        return self._sendRaw(':NUM:NORMAL:FORMAT {:s}'.format(fmt))

    def getNumberFormat(self) -> NumberFormat:
        """
        Read the number format of the output
        Available since 1.20
        """
        if not is_minimum_version(self._scpi_version, (1,20)):
            raise NotImplementedError(":NUM:NORMAL:FORMAT? requires protocol version 1.20");

        ret = self._askRaw(':NUM:NORM:FORMAT?')
        if isinstance(ret, bytes):
            format = ret.decode()
            if ' ' in format:
                format = format.split(' ')[1].rstrip()
            if format == "ASCII":
                return self.NumberFormat.ASCII
            elif format == "BIN_INTEL":
                return self.NumberFormat.BINARY_INTEL
            elif format == "BIN_MOTOROLA":
                return self.NumberFormat.BINARY_MOTOROLA
        raise Exception("Invalid NumberFormat")

    def getValueDimensions(self):
        """ Read the Dimension of the output
        Available since 1.6
        """
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

    def setValueMaxDimensions(self):
        if self.getValueDimensions():
            for idx in range(len(self._value_dimension)):
                self._sendRaw(':NUM:NORMAL:DIM{:d} MAX'.format(idx+1))
        else:
            return False
        return self.getValueDimensions()

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
        if type(data) is bytes:
            data = data.decode()
        else:
            # No Data Available or Wrong Channel
            return False
        # Remove Header if Whitespace present
        if ' ' in data:
            data = data.split(' ')[1]
        data = data.split(',')
        values = []
        if self._value_dimension is not None:
            idx = 0
            for dim in self._value_dimension:
                if dim < 2:
                    try:
                        values.append(float(data[idx]))
                        idx += 1
                        continue
                    except ValueError:
                        pass
                    except IndexError:
                        return False
                    try:
                        # Try to Parse DateTime "2017-10-10T12:16:52.33136+02:00"
                        # Variable lenght of Sub-Seconds
                        iso_ts = ''.join(data[idx].replace('"','').rsplit(':', 1))
                        timestamp = dt.datetime.strptime(iso_ts, '%Y-%m-%dT%H:%M:%S.%f%z')
                        values.append(timestamp)
                    except ValueError:
                        values.append(data[idx])
                    idx += 1
                else:
                    values.append([float(val) for val in data[idx:idx+dim]])
                    idx += dim
        else:
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
        ret = self._sendRaw(':ELOG:ITEMS {:s}'.format(channel_list_str))
        sleep(0.1)
        # Read back actual set channel names
        ret = self._askRaw(':ELOG:ITEMS?')
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':ELOG:ITEM ','')
            channel_names = ret.split('","')
            channel_names = [ch_name.replace('"','') for ch_name in channel_names]
            if len(channel_names) == 1:
                log.debug('One Channel Set: {:s}'.format(channel_names[0]))
                if channel_names[0] == 'NONE':
                    channel_names = []
                    log.warning('No Channel Set')
            self.elogChannelList = channel_names
            if len(channel_names) == 0:
                return False
            return True
        return False

    def startElog(self):
        return self._sendRaw(':ELOG:START')

    def setElogPeriod(self, period):
        return self._sendRaw(':ELOG:PERIOD {:f}'.format(period))

    def stopElog(self):
        return self._sendRaw(':ELOG:STOP')

    def setElogTimestamp(self, tsType='REL'):
        if tsType == 'REL':
            return self._sendRaw(':ELOG:TIM REL')
        if tsType == 'ABS':
            return self._sendRaw(':ELOG:TIM ABS')
        return self._sendRaw(':ELOG:TIM OFF')

    def fetchElog(self):
        data = self._askRaw(':ELOG:FETCH?')
        if type(data) is bytes:
            data = data.decode()
        else:
            return False
        if 'NONE' in data:
            return False
        # Remove Header if Whitespace present
        if ' ' in data:
            data = data.split(' ')[1]
        data = data.split(',')
        num_ch = len(self.elogChannelList)+1
        #print(len(data)/(1.0*num_ch), data)
        num_items = int(len(data)/num_ch)
        data = [data[i*num_ch:i*num_ch+num_ch] for i in range(num_items)]
        return data

    def addMarker(self, label, description=None, time=None):
        if description is None and time is None:
            return self._sendRaw(':MARK:ADD "{:s}"'.format(label))
        if description is None:
            return self._sendRaw(':MARK:ADD "{:s}",{:f}'.format(label, time))
        if time is None:
            return self._sendRaw(':MARK:ADD "{:s}","{:s}"'.format(label, description))
        return self._sendRaw(':MARK:ADD "{:s}","{:s}",{:f}'.format(label, description, time))

# TODO: Better add and remove data stream instances
class OxygenScpiDataStream:
    """
    Datastream utility class
    """
    def __init__(self, oxygen):
        self.oxygen = oxygen
        self.channel_list = []

    def setItems(self, channel_names, stream_group=1):
        """ Set Datastream Items to be transfered
        """
        if not is_minimum_version(self.oxygen._scpi_version, (1,7)):
            log.warning('SCPI Version 1.7 or higher required')
            return False
        channel_list_str = '"'+'","'.join(channel_names)+'"'
        ret = self.oxygen._sendRaw(':DST:ITEM{:d} {:s}'.format(stream_group, channel_list_str))
        sleep(0.1)
        # Read back actual set channel names
        ret = self.oxygen._askRaw(':DST:ITEM{:d}?'.format(stream_group))
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':DST:ITEM{:d} '.format(stream_group),'')
            channel_names = ret.split('","')
            channel_names = [ch_name.replace('"','') for ch_name in channel_names]
            if len(channel_names) == 1:
                log.debug('One Channel Set: {:s}'.format(channel_names[0]))
                if channel_names[0] == 'NONE':
                    channel_names = []
                    log.warning('No Channel Set')
            self.channel_list = channel_names
            if len(channel_names) == 0:
                return False
            return True
        return False

    def setTcpPort(self, tcp_port, stream_group=1):
        self.oxygen._sendRaw(':DST:PORT{:d} {:d}'.format(stream_group, tcp_port))
        return True

    def init(self, stream_group=1):
        if stream_group == 'all':
            self.oxygen._sendRaw(':DST:INIT {:s}'.format(stream_group))
        elif type(stream_group) == int:
            self.oxygen._sendRaw(':DST:INIT {:d}'.format(stream_group))
        else:
            return False
        return True

    def start(self, stream_group=1):
        if stream_group == 'all':
            self.oxygen._sendRaw(':DST:START ALL')
        elif type(stream_group) == int:
            self.oxygen._sendRaw(':DST:START {:d}'.format(stream_group))
        else:
            return False
        return True

    def stop(self, stream_group=1):
        if stream_group == 'all':
            self.oxygen._sendRaw(':DST:STOP ALL')
        elif type(stream_group) == int:
            self.oxygen._sendRaw(':DST:STOP {:d}'.format(stream_group))
        else:
            return False
        return True

    def getState(self, stream_group=1):
        ret = self.oxygen._askRaw(':DST:STAT{:d}?'.format(stream_group))
        if isinstance(ret, bytes):
            ret = ret.decode().strip()
            ret = ret.replace(':DST:STAT ','')
            return ret
        return False

    def reset(self):
        self.oxygen._sendRaw(':DST:RESET')
