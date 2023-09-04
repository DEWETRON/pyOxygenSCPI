"""
Copyright DEWETRON GmbH 2023

pyOxygenSCPI - Unit Tests
"""
import pytest
from pyOxygenSCPI import OxygenSCPI

def test_construction():
    o = OxygenSCPI('127.0.0.1')
    assert len(o.channelList) == 0
    assert len(o.elogChannelList) == 0
    assert o.DataStream is not None
    assert o.ChannelProperties is not None
    assert o.getVersion() is None
