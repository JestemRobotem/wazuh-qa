'''
brief: This module verifies the correct behavior of Wazuh Agentd during the enrollment under different configurations.
copyright:
    Copyright (C) 2015-2021, Wazuh Inc.
    Created by Wazuh, Inc. <info@wazuh.com>.
    This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
metadata:
    component:
        - Agent
    modules:
        - Agentd
    daemons:
        - Agentd
    operating_system:
        - Ubuntu
        - CentOS
        - Windows
    tiers:
        - 0
    tags:
        - Enrollment
        - Agentd
'''

import pytest
import os
import socket

from wazuh_testing.tools import LOG_FILE_PATH
from wazuh_testing.tools.services import control_service
from wazuh_testing.tools.file import load_tests, truncate_file
from wazuh_testing.tools.monitoring import FileMonitor, QueueMonitor, make_callback
from wazuh_testing.tools.configuration import load_wazuh_configurations, set_section_wazuh_conf, write_wazuh_conf
from conftest import *


# Marks
pytestmark = [pytest.mark.linux, pytest.mark.win32, pytest.mark.tier(level=0), pytest.mark.agent]

test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
tests = load_tests(os.path.join(test_data_path, 'wazuh_enrollment_tests.yaml'))
configurations_path = os.path.join(test_data_path, 'wazuh_enrollment_conf.yaml')
configurations = load_wazuh_configurations(configurations_path, __name__)
host_name = socket.gethostname()
AGENTD_TIMEOUT = 20


def get_temp_yaml(param):
    """Creates a temporal config file."""
    temp = os.path.join(test_data_path, 'temp.yaml')
    with open(configurations_path, 'r') as conf_file:
        enroll_conf = {'enrollment': {'elements': []}}
        for elem in param:
            if elem == 'password':
                continue
            enroll_conf['enrollment']['elements'].append({elem: {'value': param[elem]}})
        temp_conf_file = yaml.safe_load(conf_file)
        temp_conf_file[0]['sections'][0]['elements'].append(enroll_conf)
    with open(temp, 'w') as temp_file:
        yaml.safe_dump(temp_conf_file, temp_file)
    return temp


def override_wazuh_conf(configuration, test):
    """Re-writes Wazuh configuration file with new configurations from the test case.
    Args:
        configuration (dict): Dictionary with the configuration to overwrite.
        test (str): Name of the current test.
    """
    parse_configuration_string(configuration)
    # Configuration for testing
    temp = get_temp_yaml(configuration)
    conf = load_wazuh_configurations(temp, test, )
    os.remove(temp)

    test_config = set_section_wazuh_conf(conf[0]['sections'])
    # Set new configuration
    write_wazuh_conf(test_config)


# Fixtures

@pytest.fixture(scope='module', params=configurations)
def get_configuration(request):
    """Get configurations from the module"""
    return request.param


@pytest.mark.parametrize('test_case', [case for case in tests])
def test_agentd_enrollment(configure_environment, create_certificates, set_keys, set_pass, test_case: list):
    """
        test_logic:
            "Check that different configuration generates the adequate enrollment message or the corresponding
            error log. The configuration, keys and password files will be written with the different scenarios described
            in the test cases. After this, Agentd is started to wait for the expected result."
        checks:
            - The enrollment messages is sent when the configuration is valid
            - The enrollment message is generated as expected when the configuration is valid.
            - The error log is generated as expected when the configuration is invalid.
    """
    if 'wazuh-agentd' in test_case.get('skips', []):
        pytest.skip("This test does not apply to agentd")

    control_service('stop', daemon='wazuh-agentd')

    override_wazuh_conf(test_case.get('configuration', {}), __name__)

    if 'expected_error' in test_case:
        receiver_callback = lambda received_event: ""
        socket_listener = configure_socket_listener(receiver_callback)
        # Monitor ossec.log file
        truncate_file(LOG_FILE_PATH)
        log_monitor = FileMonitor(LOG_FILE_PATH)
        try:
            control_service('start', daemon='wazuh-agentd')
        except Exception:
            pass

        if test_case.get('expected_fail'):
            with pytest.raises(TimeoutError):
                log_monitor.start(timeout=AGENTD_TIMEOUT,
                                  callback=make_callback(test_case.get('expected_error'), prefix='.*', escape=True))
        else:
            log_monitor.start(timeout=AGENTD_TIMEOUT,
                              callback=make_callback(test_case.get('expected_error'), prefix='.*', escape=True),
                              error_message='Expected error log does not occured')
        socket_listener.shutdown()

    else:
        control_service('start', daemon='wazuh-agentd')
        test_expected = test_case['message']['expected'].format(host_name=host_name)
        test_response = test_case['message']['response'].format(host_name=host_name)
        receiver_callback = lambda received_event: test_response if test_expected.encode() == received_event else ""
        socket_listener = configure_socket_listener(receiver_callback)
        # Monitor MITM queue
        socket_monitor = QueueMonitor(socket_listener.queue)
        event = (test_expected.encode(), test_response)

        try:
            # Start socket monitoring
            socket_monitor.start(timeout=AGENTD_TIMEOUT, callback=lambda received_event: event == received_event,
                                 error_message='Enrollment request message never arrived', update_position=False)
        finally:
            socket_listener.shutdown()