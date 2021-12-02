'''
copyright: Copyright (C) 2015-2021, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: The 'wazuh-remoted' program is the server side daemon that communicates with the agents.
       Specifically, these tests will check if the agent status appears as 'disconnected' after
       just sending the 'start-up' event, sent by several agents using different protocols.
       The 'disconnected' status is when the manager considers that the agent is disconnected
       if it does not receive any keep alive messages.

tier: 0

modules:
    - remoted

components:
    - manager

daemons:
    - wazuh-remoted

os_platform:
    - linux

os_version:
    - Arch Linux
    - Amazon Linux 2
    - Amazon Linux 1
    - CentOS 8
    - CentOS 7
    - CentOS 6
    - Ubuntu Focal
    - Ubuntu Bionic
    - Ubuntu Xenial
    - Ubuntu Trusty
    - Debian Buster
    - Debian Stretch
    - Debian Jessie
    - Debian Wheezy
    - Red Hat 8
    - Red Hat 7
    - Red Hat 6

references:
    - https://documentation.wazuh.com/current/user-manual/reference/daemons/wazuh-remoted.html
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/remote.html
    - https://documentation.wazuh.com/current/user-manual/agents/agent-life-cycle.html
    - https://documentation.wazuh.com/current/user-manual/capabilities/agent-key-polling.html

tags:
    - remoted_configuration
'''
import os
import pytest
import requests
from urllib3.exceptions import InsecureRequestWarning

import wazuh_testing.remote as remote
import wazuh_testing.api as api
from wazuh_testing.tools.configuration import load_wazuh_configurations

# Marks
pytestmark = pytest.mark.tier(level=0)

# Configuration
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '')
configurations_path = os.path.join(test_data_path, 'data', 'wazuh_basic_configuration.yaml')

parameters = [
    {'ALLOWED': '127.0.0.0/24', 'DENIED': '127.0.0.1'}
]

metadata = [
    {'allowed-ips': '127.0.0.0/24', 'denied-ips': '127.0.0.1'}
]

configurations = load_wazuh_configurations(configurations_path, 'test_basic_configuration_allowed_denied_ips' , params=parameters, metadata=metadata)
configuration_ids = [f"{x['ALLOWED']}_{x['DENIED']}" for x in parameters]


# fixtures
@pytest.fixture(scope="module", params=configurations, ids=configuration_ids)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


def test_denied_ips_syslog(get_configuration, configure_environment, restart_remoted):
    '''
    description: Check that 'wazuh-remoted' deniend connection to the specified 'denied-ips'.
                 For this purpose, it uses the configuration from test cases, check if the different errors are
                 logged correctly and check if the API retrieves the expected configuration.

    wazuh_min_version: 4.2.0

    parameters:
        - get_configuration:
            type: fixture
            brief: Get configurations from the module.
        - configure_environment:
            type: fixture
            brief: Configure a custom environment for testing. Restart Wazuh is needed for applying the configuration.
        - restart_remoted:
            type: fixture
            brief: Clear the 'ossec.log' file and start a new monitor.

    assertions:
        - Verify that remoted starts correctly.
        - Verify that the warning is logged correctly in ossec.log when receives a message from blocked ip.
        - Verify that the error is logged correctly in ossec.log when receives a message from blocked ip.
        - Verify that the critical error is logged correctly in ossec.log when receives a message from blocked ip.
        - Verify that the API query matches correctly with the configuration that ossec.conf contains.
        - Verify that the selected configuration is the same as the API response.

    input_description: A configuration template (test_basic_configuration_allowed_denied_ips) is contained in an
                       external YAML file, (wazuh_basic_configuration.yaml). That template is combined with different
                       test cases defined in the module. Those include configuration settings for the 'wazuh-remoted'
                       daemon and agents info.

    expected_output:
        - r'Started <pid>: .* Listening on port .*'
        - Wazuh remoted did not start as expected.
        - r'Remote syslog allowed from: .*'
        - The expected output for denied-ips has not been produced.
        - r'Message from .* not allowed. Cannot find the ID of the agent'
        - r'API query '{protocol}://{host}:{port}/manager/configuration?section=remote' doesn't match the 
          introduced configuration on ossec.conf.'

    tags:
        - syslog
    '''
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
    cfg = get_configuration['metadata']

    log_callback = remote.callback_detect_syslog_allowed_ips(cfg['allowed-ips'])

    wazuh_log_monitor.start(timeout=5, callback=log_callback, error_message="Wazuh remoted didn't start as expected.")

    remote.send_syslog_message(message='Feb 22 13:08:48 Remoted Syslog Denied testing', port=514, protocol=remote.UDP)

    log_callback = remote.callback_detect_syslog_denied_ips(cfg['denied-ips'])

    wazuh_log_monitor.start(timeout=5, callback=log_callback,
                            error_message="The expected output for denied-ips has not been produced")

    # Check that API query return the selected configuration
    api.compare_config_api_response([cfg], 'remote')
