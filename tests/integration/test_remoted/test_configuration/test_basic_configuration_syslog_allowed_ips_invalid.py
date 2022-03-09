'''
copyright: Copyright (C) 2015-2021, Wazuh Inc.
           Created by Wazuh, Inc. <info@wazuh.com>.
           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: The 'wazuh-remoted' program is the server side daemon that communicates with the agents.
       Specifically, this test will check that 'wazuh-remoted' doesn't start and produces an error
       message when 'allowed-ips' values are invalid.

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
    - remoted
'''
import os
import pytest

import wazuh_testing.remote as remote
from wazuh_testing.tools.configuration import load_wazuh_configurations
from wazuh_testing.tools.monitoring import REMOTED_DETECTOR_PREFIX
import wazuh_testing.generic_callbacks as gc
from wazuh_testing.tools import WAZUH_CONF_RELATIVE

# Marks
pytestmark = [pytest.mark.server, pytest.mark.tier(level=0)]

# Configuration
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_basic_configuration.yaml')

parameters = [
    {'ALLOWED': '127.0.0.0.0'},
    {'ALLOWED': 'Testing'},
    {'ALLOWED': '127.0.0.0/7890'},
    {'ALLOWED': '127.0.0.0/7890'},
    {'ALLOWED': '::1::1'},
    {'ALLOWED': 'Testing'},
    {'ALLOWED': '::1/512'},
    {'ALLOWED': '::1/512'}
]

metadata = [
    {'allowed-ips': '127.0.0.0.0'},
    {'allowed-ips': 'Testing'},
    {'allowed-ips': '127.0.0.0/7890'},
    {'allowed-ips': '127.0.0.0/7890'},
    {'allowed-ips': '::1::1'},
    {'allowed-ips': 'Testing'},
    {'allowed-ips': '::1/512'},
    {'allowed-ips': '::1/512'}
]

configurations = load_wazuh_configurations(configurations_path, "test_allowed_ips_invalid",
                                           params=parameters, metadata=metadata)
configuration_ids = [f"{x['ALLOWED']}" for x in parameters]


# fixtures
@pytest.fixture(scope="module", params=configurations, ids=configuration_ids)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


def test_allowed_ips_invalid(get_configuration, configure_environment, restart_remoted):
    '''
    description: Check that 'wazuh-remoted' fails when 'allowed-ips' has invalid values.
                 For this purpose, it uses the configuration from test cases and check if the different errors are
                 logged correctly.
    
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
        - Verify that the errors is logged correctly in ossec.log whent they should be.
    
    input_description: A configuration template (test_basic_configuration_allowed_denied_ips) is contained in an
                       external YAML file, (wazuh_basic_configuration.yaml). That template is combined with different
                       test cases defined in the module. Those include configuration settings for the 'wazuh-remoted'
                       daemon and agents info.
    
    expected_output:
        - r'Started <pid>: .* Listening on port .*'
        - The expected error output has not been produced.
        - r'ERROR: .* Invalid ip address:.*'
        - r'(ERROR|CRITICAL): .* Configuration error at '.*'
    
    tags:
        - remoted
    '''
    cfg = get_configuration['metadata']

    log_callback = remote.callback_error_invalid_ip(cfg['allowed-ips'])
    wazuh_log_monitor.start(timeout=5, callback=log_callback,
                            error_message="The expected error output has not been produced")

    log_callback = gc.callback_error_in_configuration('ERROR', prefix=REMOTED_DETECTOR_PREFIX,
                                                      conf_path=WAZUH_CONF_RELATIVE)
    wazuh_log_monitor.start(timeout=5, callback=log_callback,
                            error_message="The expected error output has not been produced")

    log_callback = gc.callback_error_in_configuration('CRITICAL', prefix=REMOTED_DETECTOR_PREFIX,
                                                      conf_path=WAZUH_CONF_RELATIVE)
    wazuh_log_monitor.start(timeout=5, callback=log_callback,
                            error_message="The expected error output has not been produced")
