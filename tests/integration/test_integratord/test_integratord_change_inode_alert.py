'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.
           Created by Wazuh, Inc. <info@wazuh.com>.
           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration
brief: Integratord manages wazuh integrations with other applications such as Yara or Virustotal, by feeding
the integrated aplications with the alerts located in alerts.json file. This test module aims to validate that
given a specific alert, the expected response is recieved, depending if it is a valid/invalid json alert, an
overlong alert (64kb+) or what happens when it cannot read the file because it is missing.
components:
    - integratord
suite: integratord_read_json_alerts
targets:
    - agent
daemons:
    - wazuh-integratord
os_platform:
    - Linux
os_version:
    - Centos 8
    - Ubuntu Focal
references:
    - https://documentation.wazuh.com/current/user-manual/capabilities/virustotal-scan/integration.html
    - https://documentation.wazuh.com/current/user-manual/reference/daemons/wazuh-integratord.htm
pytest_args:
    - tier:
        0: Only level 0 tests are performed, they check basic functionalities and are quick to perform.
        1: Only level 1 tests are performed, they check functionalities of medium complexity.
        2: Only level 2 tests are performed, they check advanced functionalities and are slow to perform.
tags:
    - virustotal
'''
import os
import time
import pytest
from wazuh_testing import global_parameters
from wazuh_testing.tools import WAZUH_PATH, LOG_FILE_PATH, ALERT_FILE_PATH
from wazuh_testing.tools.file import remove_file, copy
from wazuh_testing.modules import integratord as integrator
from wazuh_testing.tools.configuration import get_test_cases_data, load_configuration_template
from wazuh_testing.tools.monitoring import FileMonitor, callback_generator


# Marks
pytestmark = [pytest.mark.server]

# Reference paths
TEST_DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
CONFIGURATIONS_PATH = os.path.join(TEST_DATA_PATH, 'configuration_template')
TEST_CASES_PATH = os.path.join(TEST_DATA_PATH, 'test_cases')

# Configuration and cases data
configurations_path = os.path.join(CONFIGURATIONS_PATH, 'config_integratord_read_json_alerts.yaml')
cases_path = os.path.join(TEST_CASES_PATH, 'cases_integratord_change_inode_alert.yaml')

# Configurations
configuration_parameters, configuration_metadata, case_ids = get_test_cases_data(cases_path)
configurations = load_configuration_template(configurations_path, configuration_parameters,
                                             configuration_metadata)
local_internal_options = {'integrator.debug': '2'}

# Variables
TEMP_FILE_PATH = os.path.join(WAZUH_PATH, 'logs/alerts/alerts.json.tmp')


# Tests
@pytest.mark.tier(level=1)
@pytest.mark.parametrize('configuration, metadata',
                         zip(configurations, configuration_metadata), ids=case_ids)
def test_integratord_change_json_inode(configuration, metadata, set_wazuh_configuration, truncate_monitored_files,
                                       configure_local_internal_options_module, restart_wazuh_function,
                                       wait_for_start_module):
    '''
    description: Check that when a given alert is inserted into alerts.json, integratord works as expected.
    wazuh_min_version: 4.3.5
    tier: 1
   parameters:
        - configuration:
            type: dict
            brief: Configuration loaded from `configuration_template`.
        - metadata:
            type: dict
            brief: Test case metadata.
        - set_wazuh_configuration:
            type: fixture
            brief: Set wazuh configuration.
        - truncate_monitored_files:
            type: fixture
            brief: Truncate all the log files and json alerts files before and after the test execution.
        - configure_local_internal_options_module:
            type: fixture
            brief: Configure the local internal options file.
        - restart_wazuh_function:
            type: fixture
            brief: Restart wazuh-modulesd daemon before starting a test, and stop it after finishing.
        - wait_for_start_module:
            type: fixture
            brief: Detect the start of the Integratord module in the ossec.log
    assertions:
        - Verify the expected response with for a given alert is recieved
    input_description:
        - The `config_integratord_read_json_alerts.yaml` file provides the module configuration for this test.
        - The `cases_integratord_read_json_alerts` file provides the test cases.
    expected_output:
        - r'.*Sending FIM event: (.+)$' ('added', 'modified' and 'deleted' events)

    '''
    sample = metadata['alert_sample']
    wazuh_monitor = FileMonitor(LOG_FILE_PATH)

    # Insert Alerts
    for n in range(5):
        os.system(f"echo '{sample}' >> {ALERT_FILE_PATH}")

    # Get that alert is read
    result = wazuh_monitor.start(timeout=global_parameters.default_timeout * 2,
                                 callback=callback_generator(integrator.CB_INTEGRATORD_SENDING_ALERT),
                                 error_message=integrator.ERR_MSG_SENDING_ALERT_NOT_FOUND,
                                 update_position=False).result()

    # Change file to change inode
    copy(ALERT_FILE_PATH, TEMP_FILE_PATH)
    remove_file(ALERT_FILE_PATH)
    copy(TEMP_FILE_PATH, ALERT_FILE_PATH)

    # Wait for Inode change to be detected and insert new alert
    time.sleep(3)
    os.system(f"echo '{sample}' >> {ALERT_FILE_PATH}")

    # Monitor Inode Changed
    result = wazuh_monitor.start(timeout=global_parameters.default_timeout * 2,
                                 callback=callback_generator(integrator.CB_ALERTS_FILE_INODE_CHANGED),
                                 error_message=integrator.ERR_MSG_ALERT_INODE_CHANGED_NOT_FOUND).result()
    os.system(f"echo '{sample}' >> {ALERT_FILE_PATH}")

    # Read Response in ossec.log
    result = wazuh_monitor.start(timeout=global_parameters.default_timeout,
                                 callback=callback_generator(integrator.CB_PROCESSING_ALERT),
                                 error_message=integrator.ERR_MSG_VIRUSTOTAL_ALERT_NOT_DETECTED).result()
