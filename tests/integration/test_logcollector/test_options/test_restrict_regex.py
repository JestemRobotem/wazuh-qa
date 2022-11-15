'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: The 'wazuh-logcollector' daemon monitors configured files and commands for new log messages.
       Specifically, these tests check the behavior of the restrict and ignore options, that allow
       users to configure regex patterns that limit if a log will be sent to analysis or will be ignored.
       The restrict causes any log that does not match the regex to be ignored, conversely, the 'ignore' option
       causes logs that match the regex to be ignored and not be sent for analysis.

components:
    - logcollector

suite: options

targets:
    - agent
    - manager

daemons:
    - wazuh-logcollector

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
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html
    - https://documentation.wazuh.com/current/user-manual/reference/statistics-files/wazuh-logcollector-state.html
    - https://documentation.wazuh.com/current/user-manual/reference/internal-options.html#logcollector

tags:
    - logcollector_options
'''
import os
import sys
import re
import pytest

from wazuh_testing.tools import PREFIX
from wazuh_testing.tools.local_actions import run_local_command_returning_output
from wazuh_testing.tools.configuration import load_configuration_template, get_test_cases_data
from wazuh_testing.modules.logcollector import event_monitor as evm
from wazuh_testing.modules import logcollector as lc


# Reference paths
TEST_DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
CONFIGURATIONS_PATH = os.path.join(TEST_DATA_PATH, 'configuration_template')
TEST_CASES_PATH = os.path.join(TEST_DATA_PATH, 'test_cases')

# Configuration and cases data
t1_configurations_path = os.path.join(CONFIGURATIONS_PATH, 'configuration_restrict_regex_default.yaml')
t1_cases_path = os.path.join(TEST_CASES_PATH, 'cases_restrict_regex_default.yaml')

t2_configurations_path = os.path.join(CONFIGURATIONS_PATH, 'configuration_restrict_regex_type_values.yaml')
t2_cases_path = os.path.join(TEST_CASES_PATH, 'cases_restrict_regex_type_values.yaml')

# Test configurations
test_file = os.path.join(PREFIX, 'test')

t1_configuration_parameters, t1_configuration_metadata, t1_case_ids = get_test_cases_data(t1_cases_path)
for count, value in enumerate(t1_configuration_parameters):
    t1_configuration_parameters[count]['LOCATION'] = test_file
t1_configurations = load_configuration_template(t1_configurations_path, t1_configuration_parameters,
                                                t1_configuration_metadata)

t2_configuration_parameters, t2_configuration_metadata, t2_case_ids = get_test_cases_data(t2_cases_path)
for count, value in enumerate(t2_configuration_parameters):
    t2_configuration_parameters[count]['LOCATION'] = test_file
t2_configurations = load_configuration_template(t2_configurations_path, t2_configuration_parameters,
                                                t2_configuration_metadata)

prefix = lc.LOG_COLLECTOR_PREFIX


# Tests
@pytest.mark.tier(level=1)
@pytest.mark.parametrize('new_file_path,', [test_file], ids=[''])
@pytest.mark.parametrize('local_internal_options,', [lc.LOGCOLLECTOR_DEFAULT_LOCAL_INTERNAL_OPTIONS], ids=[''])
@pytest.mark.parametrize('configuration, metadata', zip(t1_configurations, t1_configuration_metadata), ids=t1_case_ids)
def test_restrict_default(configuration, metadata, new_file_path, create_file, truncate_monitored_files,
                          local_internal_options, set_wazuh_configuration_with_local_internal_options,
                          restart_wazuh_function):
    '''
    description: Check if logcollector reads or ignores a log according to a regex configured in the restrict tag for a
    given log file.

    test_phases:
        - Set a custom Wazuh configuration.
        - Restart monitord.
        - Insert the log message.
        - Check expected response.

    wazuh_min_version: 4.5.0

    tier: 1

    parameters:
        - configuration:
            type: dict
            brief: Wazuh configuration data. Needed for set_wazuh_configuration fixture.
        - metadata:
            type: dict
            brief: Wazuh configuration metadata
        - new_file_path:
            type: str
            brief: path for the log file to be created and deleted after the test.
        - local_internal_options
            type: dict
            brief: Contains the options to configure in local_internal_options
        - create_file:
            type: fixture
            brief: Create an empty file for logging
        - truncate_monitored_files:
            type: fixture
            brief: Truncate all the log files and json alerts files before and after the test execution.
        - set_wazuh_configuration_with_local_internal_options:
            type: fixture
            brief: Set the wazuh configuration according to the configuration data and local_internal_options.
        - restart_wazuh_function:
            type: fixture
            brief: Restart wazuh.

    assertions:
        - Check that logcollector is analyzing the log file.
        - Check that logs are ignored when they do not match with configured regex

    input_description:
        - The `configuration_ignore_regex_default.yaml` file provides the module configuration for this test.
        - The `cases_ignore_regex_default` file provides the test cases.

    expected_output:
        - r".*wazuh-logcollector.*Analizing file: '{file}'.*"
        - r".*wazuh-logcollector.*DEBUG: Reading syslog '{message}'.*"
        - r".*wazuh-logcollector.*DEBUG: Ignoring the log line '{message}' due to {tag} config: '{regex}'"
    '''
    log = metadata['log_sample']
    command = f"echo {log}>> {test_file}"

    if sys.platform == 'win32':
        file = re.escape(test_file)
    else:
        file = test_file

    # Check log file is being analized
    evm.check_analyzing_file(file=file, prefix=prefix)

    #  Insert log
    run_local_command_returning_output(command)
    # Check the log is read from the monitored file
    evm.check_syslog_messages(message=log, prefix=prefix)
    # Check response
    if metadata['matches']:
        log_found = False
        with pytest.raises(TimeoutError):
            log_found = evm.check_ignore_restrict_messages(message=log, regex=metadata['regex'], tag='restrict',
                                                           prefix=prefix)
        assert log_found is False, lc.ERR_MSG_UNEXPECTED_IGNORE_EVENT
    else:
        evm.check_ignore_restrict_messages(message=log, regex=metadata['regex'], tag='restrict',
                                           prefix=prefix)


@pytest.mark.tier(level=1)
@pytest.mark.parametrize('new_file_path,', [test_file], ids=[''])
@pytest.mark.parametrize('local_internal_options,', [lc.LOGCOLLECTOR_DEFAULT_LOCAL_INTERNAL_OPTIONS], ids=[''])
@pytest.mark.parametrize('configuration, metadata', zip(t2_configurations, t2_configuration_metadata), ids=t2_case_ids)
def test_restrict_regex_type_values(configuration, metadata, new_file_path, create_file, truncate_monitored_files,
                                    local_internal_options, set_wazuh_configuration_with_local_internal_options,
                                    restart_wazuh_function):
    '''
    description: Check if logcollector reads or ignores a log according to a regex configured in the restrict tag for a
    given log file, with each configured value for the restrict 'type' attribute value configured.

    test_phases:
        - Set a custom Wazuh configuration.
        - Restart monitord.
        - Insert the log message.
        - Check expected response.

    wazuh_min_version: 4.5.0

    tier: 1

    parameters:
        - configuration:
            type: dict
            brief: Wazuh configuration data. Needed for set_wazuh_configuration fixture.
        - metadata:
            type: dict
            brief: Wazuh configuration metadata
        - new_file_path:
            type: str
            brief: path for the log file to be created and deleted after the test.
        - local_internal_options
            type: dict
            brief: Contains the options to configure in local_internal_options
        - create_file:
            type: fixture
            brief: Create an empty file for logging
        - truncate_monitored_files:
            type: fixture
            brief: Truncate all the log files and json alerts files before and after the test execution.
        - set_wazuh_configuration_with_local_internal_options:
            type: fixture
            brief: Set the wazuh configuration according to the configuration data and local_internal_options.
        - restart_wazuh_function:
            type: fixture
            brief: Restart wazuh.

    assertions:
        - Check that logcollector is analyzing the log file.
        - Check that logs are ignored when they do not match with configured regex

    input_description:
        - The `configuration_ignore_regex_default.yaml` file provides the module configuration for this test.
        - The `cases_ignore_regex_default` file provides the test cases.

    expected_output:
        - r".*wazuh-logcollector.*Analizing file: '{file}'.*"
        - r".*wazuh-logcollector.*DEBUG: Reading syslog '{message}'.*"
        - r".*wazuh-logcollector.*DEBUG: Ignoring the log line '{message}' due to {tag} config: '{regex}'"
    '''
    log = metadata['log_sample']
    command = f"echo {log}>> {test_file}"

    if sys.platform == 'win32':
        file = re.escape(test_file)
    else:
        file = test_file

    # Check log file is being analized
    evm.check_analyzing_file(file=file, prefix=prefix)

    #  Insert log
    run_local_command_returning_output(command)
    # Check the log is read from the monitored file
    evm.check_syslog_messages(message=log, prefix=prefix)
    # Check response
    if metadata['matches']:
        log_found = False
        with pytest.raises(TimeoutError):
            log_found = evm.check_ignore_restrict_messages(message=log, regex=metadata['regex'], tag='restrict',
                                                           prefix=prefix)
        assert log_found is False, lc.ERR_MSG_UNEXPECTED_IGNORE_EVENT
    else:
        evm.check_ignore_restrict_messages(message=log, regex=metadata['regex'], tag='restrict',
                                           prefix=prefix)
