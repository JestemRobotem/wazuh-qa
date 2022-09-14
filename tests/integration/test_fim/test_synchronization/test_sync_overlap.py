'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: 

components:
    - fim

suite: synchronization

targets:
    - agent
    - manager

daemons:
    - wazuh-syscheckd

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
    - https://documentation.wazuh.com/current/user-manual/capabilities/file-integrity/index.html
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/syscheck.html#synchronization

pytest_args:
    - fim_mode:
        realtime: Enable real-time monitoring on Linux (using the 'inotify' system calls) and Windows systems.
        whodata: Implies real-time monitoring but adding the 'who-data' information.
    - tier:
        0: Only level 0 tests are performed, they check basic functionalities and are quick to perform.
        1: Only level 1 tests are performed, they check functionalities of medium complexity.
        2: Only level 2 tests are performed, they check advanced functionalities and are slow to perform.

tags:
    - fim_synchronization
'''
import os

import pytest
from wazuh_testing import global_parameters
from wazuh_testing.tools import PREFIX, LOG_FILE_PATH, configuration
from wazuh_testing.tools.file import delete_path_recursively
from wazuh_testing.tools.monitoring import FileMonitor, generate_monitoring_callback
from wazuh_testing.fim import REGULAR, callback_detect_synchronization, create_file


# Marks
# pytestmark = [pytest.mark.linux, pytest.mark.tier(level=2)]

# Reference paths
TEST_DATA_PATH  = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
CONFIGURATIONS_PATH = os.path.join(TEST_DATA_PATH, 'configuration_template')
TEST_CASES_PATH = os.path.join(TEST_DATA_PATH, 'test_cases') 

# Configuration and cases data
test_cases_path = os.path.join(TEST_CASES_PATH, 'cases_sync_overlap.yaml')
configurations_path = os.path.join(CONFIGURATIONS_PATH, 'configuration_sync_overlap.yaml')

# Test configurations
configuration_parameters, configuration_metadata, test_case_ids = configuration.get_test_cases_data(test_cases_path)
configurations = configuration.load_configuration_template(configurations_path, configuration_parameters,
                                                           configuration_metadata)

# Variables 
test_directories = os.path.join(PREFIX, 'testdir')
wazuh_log_monitor = FileMonitor(LOG_FILE_PATH)

# Tests
@pytest.mark.parametrize('daemon', ["wazuh-syscheckd"])
@pytest.mark.parametrize('configuration, metadata', zip(configurations, configuration_metadata), ids=test_case_ids) 
def test_sync_overlap(configuration, metadata, daemon, set_wazuh_configuration_fim, truncate_monitored_files, restart_syscheck_function, wait_for_fim_start_function):
    '''
    description: Check if the 'wazuh-syscheckd' daemon performs the file synchronization at the intervals
                 specified in the configuration, using the 'interval' tag. For this purpose, the test
                 will monitor a testing directory. Then, it will travel in time to the next synchronization
                 time and verify that the FIM 'integrity' event is trigered. Finally, the test will travel
                 in time to half of the interval and verify that no FIM 'integrity' event is generated.

    wazuh_min_version: 4.5.0

    tier: 1

    parameters:
        - get_configuration:
            type: fixture
            brief: Get configurations from the module.
        - configure_environment:
            type: fixture
            brief: Configure a custom environment for testing.
        - restart_syscheckd:
            type: fixture
            brief: Clear the 'ossec.log' file and start a new monitor.
        - wait_for_fim_start:
            type: fixture
            brief: Wait for realtime start, whodata start, or end of initial FIM scan.

    assertions:
        - Verify that FIM 'integrity' event is generated when the interval specified has elapsed.
        - Verify that no FIM 'integrity' event is generated at half of the interval specified.

    input_description: A test case (sync_interval) is contained in external YAML file (wazuh_conf.yaml) which
                       includes configuration settings for the 'wazuh-syscheckd' daemon. That is combined with
                       the interval periods and the testing directory to be monitored defined in this module.

    expected_output:
        - r'Initializing FIM Integrity Synchronization check'

    tags:
        - scheduled

    '''
    # Create files
    for file in range(0,metadata['files']):
        create_file(REGULAR, test_directories, f"test_file_{file}")
    
    # Wait for sync to start
    wazuh_log_monitor.start(timeout=global_parameters.default_timeout, callback=callback_detect_synchronization,
                            error_message='Did not receive expected '
                                          '"Initializing FIM Integrity Synchronization check" event', update_position=True).result()
    # Check if timeout, sync_interval doubled
    
    # Check if new fim scan was launched no new sync started.
    # Check when sync ends sync_interval is returned to normal.

    # Delete files and folder
    delete_path_recursively(test_directories)