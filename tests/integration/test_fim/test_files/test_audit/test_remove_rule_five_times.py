# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2


import os
import subprocess

import pytest
import wazuh_testing.fim as fim
from wazuh_testing.tools.configuration import load_wazuh_configurations, check_apply_test
from wazuh_testing.tools.monitoring import FileMonitor

# Marks

pytestmark = [pytest.mark.linux, pytest.mark.tier(level=1)]

# Variables

test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_conf.yaml')
test_directories = [os.path.join('/', 'testdir1'), os.path.join('/', 'testdir2'), os.path.join('/', 'testdir3')]
testdir1, testdir2, testdir3 = test_directories

wazuh_log_monitor = FileMonitor(fim.LOG_FILE_PATH)

# Configurations

configurations = load_wazuh_configurations(configurations_path, __name__)


# Fixture

@pytest.fixture(scope='module', params=configurations)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


# Test

@pytest.mark.parametrize('tags_to_apply, folder, audit_key', [
    ({'config1'}, '/testdir2', 'wazuh_fim')
])
def test_remove_rule_five_times(tags_to_apply, folder, audit_key,
                                get_configuration, configure_environment, restart_syscheckd, wait_for_fim_start):
    """Remove auditd rule using auditctl five times and check Wazuh ignores folder.

    Args:
        tags_to_apply (set): Run test if matches with a configuration identifier, skip otherwise.
        folder (str): Path whose rule will be removed.
        audit_key (str): Name of the configured audit key.
        get_configuration (fixture): Gets the current configuration of the test.
        uninstall_install_audit (fixture): Uninstall auditd before the test and install auditd again after the test is
                                           executed.
        configure_environment (fixture): Configure the environment for the execution of the test.
        restart_syscheckd (fixture): Restarts syscheck.
        wait_for_fim_start (fixture): Waits until the first FIM scan is completed.

    Raises:
        TimeoutError: If an expected event couldn't be captured.
    """

    check_apply_test(tags_to_apply, get_configuration['tags'])

    for _ in range(0, 5):
        subprocess.run(["auditctl", "-W", folder, "-p", "wa", "-k", audit_key], check=True)
        wazuh_log_monitor.start(timeout=20, callback=fim.callback_audit_rules_manipulation,
                                error_message='Did not receive expected '
                                              '"Detected Audit rules manipulation" event')

    wazuh_log_monitor.start(timeout=20, callback=fim.callback_audit_deleting_rule,
                            error_message='Did not receive expected "Deleting Audit rules" event')
