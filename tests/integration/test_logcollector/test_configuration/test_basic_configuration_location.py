'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: The 'wazuh-logcollector' daemon monitors configured files and commands for new log messages.
       Specifically, these tests will check if the Wazuh component (agent or manager) starts when
       the 'location' tag is set in the configuration, and the Wazuh API returns the same values for
       the configured 'localfile' section.
       Log data collection is the real-time process of making sense out of the records generated by
       servers or devices. This component can receive logs through text files or Windows event logs.
       It can also directly receive logs via remote syslog which is useful for firewalls and
       other such devices.

tier: 0

modules:
    - logcollector

components:
    - agent
    - manager

daemons:
    - wazuh-logcollector
    - wazuh-apid

os_platform:
    - linux
    - windows

os_version:
    - Arch Linux
    - Amazon Linux 2
    - Amazon Linux 1
    - CentOS 8
    - CentOS 7
    - Debian Buster
    - Red Hat 8
    - Ubuntu Focal
    - Ubuntu Bionic
    - Windows 10
    - Windows Server 2019
    - Windows Server 2016

references:
    - https://documentation.wazuh.com/current/user-manual/capabilities/log-data-collection/index.html
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#location
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#log-format

tags:
    - logcollector
'''

import sys
import os
import pytest
import tempfile

import wazuh_testing.api as api
from wazuh_testing.tools.configuration import load_wazuh_configurations
from wazuh_testing.tools import get_service, LOG_FILE_PATH
from wazuh_testing.tools.services import check_if_process_is_running
from wazuh_testing.tools.utils import lower_case_key_dictionary_array
from wazuh_testing.tools.monitoring import FileMonitor
from wazuh_testing.logcollector import WINDOWS_CHANNEL_LIST, callback_eventchannel_bad_format, \
    LOG_COLLECTOR_GLOBAL_TIMEOUT

# Marks
pytestmark = pytest.mark.tier(level=0)

# Configuration
no_restart_windows_after_configuration_set = True
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_basic_configuration.yaml')

wazuh_component = get_service()

folder_path = tempfile.gettempdir()

parameters = [
    {'LOCATION': f"{os.path.join(folder_path, 'test.txt')}", 'LOG_FORMAT': 'syslog'},
    {'LOCATION': f"{os.path.join(folder_path, '*')}", 'LOG_FORMAT': 'syslog'},
    {'LOCATION': f"{os.path.join(folder_path, 'Testing white spaces')}", 'LOG_FORMAT': 'syslog'},
    {'LOCATION': fr"{os.path.join(folder_path, '%F%H%K%L')}", 'LOG_FORMAT': 'syslog'},
    {'LOCATION': fr"{os.path.join(folder_path, 'test.*')}", 'LOG_FORMAT': 'syslog'},
    {'LOCATION': fr"{os.path.join(folder_path, 'c*test.txt')}", 'LOG_FORMAT': 'syslog'},
    {'LOCATION': fr"{os.path.join(folder_path, '?¿^*We.- Nmae')}", 'LOG_FORMAT': 'syslog'},
    {'LOCATION': fr"{os.path.join(folder_path, 'file.log-%Y-%m-%d')}", 'LOG_FORMAT': 'syslog'},
]

windows_parameters = []
invalid_channel = 'invalidchannel'
for channel in WINDOWS_CHANNEL_LIST:
    windows_parameters.append({'LOCATION': f'{channel}', 'LOG_FORMAT': 'eventchannel'})
windows_parameters.append({'LOCATION': f'{invalid_channel}', 'LOG_FORMAT': 'eventchannel'})

macos_parameters = [{'LOCATION': 'macos', 'LOG_FORMAT': 'macos'}]

if sys.platform == 'win32':
    parameters += windows_parameters
elif sys.platform == 'darwin':
    parameters += macos_parameters

metadata = lower_case_key_dictionary_array(parameters)

configurations = load_wazuh_configurations(configurations_path, __name__,
                                           params=parameters,
                                           metadata=metadata)
configuration_ids = [f"{x['location']}_{x['log_format']}" for x in metadata]


# fixtures
@pytest.fixture(scope="module", params=configurations, ids=configuration_ids)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


@pytest.mark.filterwarnings('ignore::urllib3.exceptions.InsecureRequestWarning')
def test_configuration_location(get_configuration, configure_environment, restart_logcollector):
    '''
    description: Check if the 'wazuh-logcollector' daemon starts properly when the 'location' tag is used.
                 For this purpose, the test will configure the logcollector to monitor a 'syslog' directory
                 and use a pathname with special characteristics. Finally, the test will verify that the
                 Wazuh component is started by checking its process, and the Wazuh API returns the same
                 values for the 'localfile' section that the configured one.

    wazuh_min_version: 4.2.0

    tier: 0

    parameters:
        - get_configuration:
            type: fixture
            brief: Get configurations from the module.
        - configure_environment:
            type: fixture
            brief: Configure a custom environment for testing.
        - restart_logcollector:
            type: fixture
            brief: Clear the 'ossec.log' file and start a new monitor.

    assertions:
        - Verify that the Wazuh component (agent or manager) can start when the 'location' tag is used.
        - Verify that the Wazuh API returns the same value for the 'localfile' section as the configured one.
        - Verify that the expected event is present in the log file.

    input_description: A configuration template (test_basic_configuration_location) is contained in an external
                       YAML file (wazuh_basic_configuration.yaml). That template is combined with different
                       test cases defined in the module. Those include configuration settings for
                       the 'wazuh-logcollector' daemon.

    expected_output:
        - Boolean values to indicate the state of the Wazuh component.
        - Did not receive the expected "ERROR: Could not EvtSubscribe() for ... which returned ..." event.

    tags:
        - invalid_settings
    '''
    cfg = get_configuration['metadata']

    if wazuh_component == 'wazuh-manager':
        api.wait_until_api_ready()
        api.compare_config_api_response([cfg], 'localfile')
    else:
        if sys.platform == 'win32':
            assert check_if_process_is_running('wazuh-agent.exe') == True
            if cfg['location'] == invalid_channel:
                log_monitor = FileMonitor(LOG_FILE_PATH)
                callback = callback_eventchannel_bad_format(invalid_channel)
                log_monitor.start(timeout=LOG_COLLECTOR_GLOBAL_TIMEOUT, callback=callback,
                                  error_message='Did not receive the expected "ERROR: Could not EvtSubscribe() for ...'
                                  ' which returned ..." event.')
        else:
            check_if_process_is_running('wazuh-logcollector')
