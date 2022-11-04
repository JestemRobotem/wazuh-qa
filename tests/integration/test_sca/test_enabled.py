'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: These tests will check if the `enabled` option of the Vulnerability Detector module
       is working correctly. This option is located in its corresponding section of
       the `ossec.conf` file and allows enabling or disabling this module.

components:
    - vulnerability_detector

suite: general_settings

targets:
    - manager

daemons:
    - wazuh-modulesd
    - wazuh-db
    - wazuh-analysisd

os_platform:
    - linux

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

references:
    - https://documentation.wazuh.com/current/user-manual/capabilities/vulnerability-detection/index.html
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/vuln-detector.html#enabled

tags:
    - general_settings
    - settings
    - vulnerability
    - vulnerability_detector
'''
import os
import pytest

from wazuh_testing.tools.configuration import load_configuration_template, get_test_cases_data
from wazuh_testing.modules import sca
from wazuh_testing.modules.sca import event_monitor as evm
from wazuh_testing.modules.sca import SCA_DEFAULT_LOCAL_INTERNAL_OPTIONS as local_internal_options


pytestmark = [pytest.mark.server]

# Reference paths
TEST_DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
CONFIGURATIONS_PATH = os.path.join(TEST_DATA_PATH, 'configuration_template')
TEST_CASES_PATH = os.path.join(TEST_DATA_PATH, 'test_cases')

# Configuration and cases data
configurations_path = os.path.join(CONFIGURATIONS_PATH, 'configuration_enabled.yaml')
t1_cases_path = os.path.join(TEST_CASES_PATH, 'cases_enabled.yaml')
# t2_cases_path = os.path.join(TEST_CASES_PATH, 'cases_disabled.yaml')

# Enabled test configurations (t1)
t1_configuration_parameters, t1_configuration_metadata, t1_case_ids = get_test_cases_data(t1_cases_path)
t1_configurations = load_configuration_template(configurations_path, t1_configuration_parameters,
                                                t1_configuration_metadata)
# Disabled test configurations (t2)
# t2_configuration_parameters, t2_configuration_metadata, t2_case_ids = get_test_cases_data(t2_cases_path)
# t2_configurations = load_configuration_template(configurations_path, t2_configuration_parameters,
#                                                t2_configuration_metadata)


@pytest.mark.tier(level=0)
@pytest.mark.parametrize('configuration, metadata', zip(t1_configurations, t1_configuration_metadata), ids=t1_case_ids)
def test_enabled(configuration, metadata, set_wazuh_configuration, truncate_monitored_files,
                 restart_wazuh_function):
    '''
    description: Check that sca is started when is set enabled yes.

    test_phases:
        - Set a custom Wazuh configuration.
        - Restart wazuh-modulesd.
        - Check in the log that the sca module started appears.

    wazuh_min_version: 4.5.0

    tier: 0

    parameters:
        - configuration:
            type: dict
            brief: Wazuh configuration data. Needed for set_wazuh_configuration fixture.
        - metadata:
            type: dict
            brief: Wazuh configuration metadata.
        - set_wazuh_configuration:
            type: fixture
            brief: Set the wazuh configuration according to the configuration data.
        - truncate_monitored_files:
            type: fixture
            brief: Truncate all the log files and json alerts files before and after the test execution.
        - restart_modulesd_function:
            type: fixture
            brief: Restart the wazuh-modulesd daemon.

    assertions:
        - Verify that when the `enabled` option is set to `yes`, the Vulnerability Detector module is running.

    input_description:
        - The `test_enabled.yaml` file provides the module configuration for this test.

    expected_output:
        - r'NOT (.*)wazuh-modulesd:vulnerability-detector(.*) Module disabled. Exiting...'
    '''
    evm.check_sca_enabled()