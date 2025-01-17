'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: The 'wazuh-logcollector' daemon monitors configured files and commands for new log messages.
       Specifically, these tests will check if the 'only-future-events' option of the logcollector
       works properly. Log data collection is the real-time process of making sense out of
       the records generated by servers or devices. This component can receive logs through
       text files or Windows event logs. It can also directly receive logs via remote syslog
       which is useful for firewalls and other such devices.

components:
    - logcollector

suite: only_future_events

targets:
    - agent
    - manager

daemons:
    - wazuh-logcollector

os_platform:
    - linux
    - macos
    - solaris

os_version:
    - Arch Linux
    - Amazon Linux 2
    - Amazon Linux 1
    - CentOS 8
    - CentOS 7
    - Debian Buster
    - Red Hat 8
    - Solaris 10
    - Solaris 11
    - macOS Catalina
    - macOS Server
    - Ubuntu Focal
    - Ubuntu Bionic

references:
    - https://documentation.wazuh.com/current/user-manual/capabilities/log-data-collection/index.html
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#only-future-events

tags:
    - logcollector_only_future_events
'''
import os
import tempfile
import sys
import pytest

from wazuh_testing import T_10, T_20
import wazuh_testing.logcollector as logcollector
from wazuh_testing.tools.services import control_service
from wazuh_testing.tools.configuration import load_configuration_template, get_test_cases_data
from wazuh_testing.modules.logcollector import LOG_COLLECTOR_PREFIX, WINDOWS_AGENT_PREFIX, \
                                               GENERIC_CALLBACK_ERROR_COMMAND_MONITORING
from wazuh_testing.modules.logcollector import event_monitor as evm


pytestmark = [pytest.mark.tier(level=0)]

# Reference paths
TEST_DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
CONFIGURATIONS_PATH = os.path.join(TEST_DATA_PATH, 'configuration_template')
TEST_CASES_PATH = os.path.join(TEST_DATA_PATH, 'test_cases')

# Configuration and cases data
t1_configurations_path = os.path.join(CONFIGURATIONS_PATH, 'configuration_only_future_events.yaml')
t1_cases_path = os.path.join(TEST_CASES_PATH, 'cases_only_future_events.yaml')

temp_dir = tempfile.gettempdir()
log_test_path = os.path.join(temp_dir, 'wazuh-testing', 'test.log')
LOG_LINE = 'Jan  1 00:00:00 localhost test[0]: line='
prefix = LOG_COLLECTOR_PREFIX
local_internal_options = {'logcollector.vcheck_files': '5', 'logcollector.debug': '2', 'windows.debug': '2'}

if sys.platform == 'win32':
    prefix = WINDOWS_AGENT_PREFIX

# Only_future_events values test configurations (t1)
t1_configuration_parameters, t1_configuration_metadata, t1_case_ids = get_test_cases_data(t1_cases_path)

for index in range(len(t1_configuration_metadata)):
    t1_configuration_metadata[index]['location'] = log_test_path
    t1_configuration_parameters[index]['LOCATION'] = log_test_path

t1_configurations = load_configuration_template(t1_configurations_path, t1_configuration_parameters,
                                                t1_configuration_metadata)

# Configuration
LOGCOLLECTOR_DAEMON = "wazuh-logcollector"

file_structure = [
    {
        'folder_path': os.path.join(temp_dir, 'wazuh-testing'),
        'filename': ['test.log'],
        'content': LOG_LINE,
        'size_kib': 10240
    }
]


@pytest.fixture(scope="module")
def get_files_list():
    """Get file list to create from the module."""
    return file_structure


@pytest.mark.parametrize('configuration, metadata', zip(t1_configurations, t1_configuration_metadata), ids=t1_case_ids)
def test_only_future_events(configuration, metadata, set_wazuh_configuration,
                            configure_local_internal_options_module, setup_log_monitor, get_files_list,
                            create_file_structure_module, restart_wazuh_daemon_function):
    '''
    description: Check if the 'only-future-events' option is used properly by the 'wazuh-logcollector' when
                 monitoring a log file. This option allows reading new log content since the logcollector
                 was stopped.

    test_phases:
        - setup:
            - Load Wazuh light configuration.
            - Apply ossec.conf configuration changes according to the configuration template and use case.
            - Apply custom settings in local_internal_options.conf.
            - Create the specified file tree structure.
            - Truncate wazuh logs.
            - Restart wazuh-manager service to apply configuration changes.
        - test:
            - Start the log monitor and check the log in `ossec.log` that the respective file is being analyzed.
            - Add n log lines corresponding to 1KB.
            - Check that the last written line has been read by logcollector.
            - Stop logcollector daemon
            - Add additional n log lines corresponding to 1KB when logcollector is stopped
            - Start logcollector daemon
            - If only_future_events is set to no, check that all written lines have been read.
            - If only_future_events is set to yes, check that all written lines have not been read.
            - If only_future_events is set to yes, write new lines and check that they are read when logcollector is on.
        - tierdown:
            - Truncate wazuh logs.
            - Restore initial configuration, both ossec.conf and local_internal_options.conf.

    wazuh_min_version: 4.2.0

    tier: 0

    parameters:
        - configuration:
            type: dict
            brief: Get configurations from the module.
        - metadata:
            type: dict
            brief: Get metadata from the module.
        - set_wazuh_configuration:
            type: fixture
            brief: Apply changes to the ossec.conf configuration.
        - configure_local_internal_options_module:
            type: fixture
            brief: Configure the Wazuh local internal options file.
        - setup_log_monitor:
            type: fixture
            brief: Create the log monitor.
        - get_files_list:
            type: fixture
            brief: Get file list to create from the module.
        - create_file_structure_module:
            type: fixture
            brief: Create the specified file tree structure.
        - restart_wazuh_daemon_function:
            type: fixture
            brief: Restart the wazuh service.

    assertions:
        - Verify that the logcollector starts monitoring the log file.
        - Verify that the logcollector detects data addition on a monitored log file.
        - Verify that the logcollector detects the logs messages generated while it stopped
          when it is started, and the 'only-future-events' option is disabled.
        - Verify that the logcollector ignores the logs messages generated while it stopped
          when it is started, and the 'only-future-events' option is enabled.
        - Verify that the log collector continues detecting new logs messages when it is started.

    input_description: A configuration template (test_only_future_events) is contained in an external YAML file
                       (configuration_only_future_events.yaml). That template is combined with two test cases defined
                       in the file cases_only_future_events.yaml.

    expected_output:
        - r'Analyzing file.*'
        - r'Reading syslog message.*'
    '''
    current_line = 0
    log_monitor = setup_log_monitor

    # Ensure that the file is being analyzed
    evm.check_analyzing_file(file_monitor=log_monitor, file=log_test_path,
                             error_message=GENERIC_CALLBACK_ERROR_COMMAND_MONITORING, prefix=prefix)

    # Add n log lines corresponding to 1KB
    current_line = logcollector.add_log_data(log_path=metadata['location'], log_line_message=LOG_LINE,
                                             size_kib=1, line_start=current_line + 1, print_line_num=True)

    # Check that the last written line has been read by logcollector
    last_line = current_line + 1
    message = f"{LOG_LINE}{last_line}"
    evm.check_syslog_messages(file_monitor=log_monitor, message=message,
                              error_message=GENERIC_CALLBACK_ERROR_COMMAND_MONITORING, prefix=prefix,
                              timeout=T_10, escape=True)
    # Stop logcollector daemon
    control_service('stop', daemon=LOGCOLLECTOR_DAEMON)

    # Add additional n log lines corresponding to 1KB when logcollector is stopped
    first_next_line = last_line + 1
    current_line = logcollector.add_log_data(log_path=metadata['location'], log_line_message=LOG_LINE,
                                             size_kib=1, line_start=first_next_line, print_line_num=True)
    # Start logcollector daemon
    control_service('start', daemon=LOGCOLLECTOR_DAEMON)

    # Logcollector should detect all written lines when logcollector was stopped
    if metadata['only_future_events'] == 'no':
        # Check first log line
        message = f"{LOG_LINE}{first_next_line}"
        evm.check_syslog_messages(file_monitor=log_monitor, message=message,
                                  error_message=GENERIC_CALLBACK_ERROR_COMMAND_MONITORING, prefix=prefix,
                                  timeout=T_20, escape=True)
        # Check last log line
        message = f"{LOG_LINE}{current_line + 1}"
        evm.check_syslog_messages(file_monitor=log_monitor, message=message,
                                  error_message=GENERIC_CALLBACK_ERROR_COMMAND_MONITORING, prefix=prefix,
                                  timeout=T_20, escape=True)
    # if only_future_events yes, logcollector should NOT detect the log lines written while it was stopped
    else:
        message = f"{LOG_LINE}{first_next_line}"
        # Check that the first written line is not read
        with pytest.raises(TimeoutError):
            message = f"{LOG_LINE}{first_next_line}"
            evm.check_syslog_messages(file_monitor=log_monitor, message=message,
                                      error_message=GENERIC_CALLBACK_ERROR_COMMAND_MONITORING, prefix=prefix,
                                      timeout=T_10, escape=True)

        # Check that the last written line is not read
        with pytest.raises(TimeoutError):
            # Check last line
            message = f"{LOG_LINE}{current_line + 1}"
            evm.check_syslog_messages(file_monitor=log_monitor, message=message,
                                      error_message=GENERIC_CALLBACK_ERROR_COMMAND_MONITORING, prefix=prefix,
                                      timeout=T_10, escape=True)

        # Check that if we write new data when the daemon is turned on, it is read normally
        current_line = logcollector.add_log_data(log_path=metadata['location'], log_line_message=LOG_LINE,
                                                 size_kib=1, line_start=current_line + 1, print_line_num=True)
        message = f"{LOG_LINE}{current_line + 1}"
        evm.check_syslog_messages(file_monitor=log_monitor, message=message,
                                  error_message=GENERIC_CALLBACK_ERROR_COMMAND_MONITORING, prefix=prefix,
                                  timeout=T_10, escape=True)
