# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
import os

import pytest
import wazuh_testing.fim as fim

from test_fim.test_files.test_follow_symbolic_link.common import configurations_path, testdir1, \
    modify_symlink, testdir_link, wait_for_symlink_check, testdir_target, testdir_not_target
# noinspection PyUnresolvedReferences
from test_fim.test_files.test_follow_symbolic_link.common import test_directories, extra_configuration_after_yield, \
    extra_configuration_before_yield
from wazuh_testing import logger
from wazuh_testing.tools.configuration import load_wazuh_configurations, check_apply_test
from wazuh_testing.tools.monitoring import FileMonitor

# All tests in this module apply to linux only
pytestmark = [pytest.mark.agent, pytest.mark.linux, pytest.mark.sunos5, pytest.mark.darwin, pytest.mark.tier(level=1)]
wazuh_log_monitor = FileMonitor(fim.LOG_FILE_PATH)

# configurations

conf_params, conf_metadata = fim.generate_params(extra_params={'FOLLOW_MODE': 'yes'})
configurations = load_wazuh_configurations(configurations_path, __name__,
                                           params=conf_params,
                                           metadata=conf_metadata
                                           )


# fixtures

@pytest.fixture(scope='module', params=configurations)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


# tests

@pytest.mark.parametrize('tags_to_apply, main_folder, aux_folder', [
    ({'monitored_file'}, testdir1, testdir_not_target),
    ({'monitored_dir'}, testdir_target, testdir_not_target)
])
def test_symbolic_change_target(tags_to_apply, main_folder, aux_folder, get_configuration, configure_environment,
                                restart_syscheckd, wait_for_fim_start):
    """Check if syscheck updates the symlink target properly

    Having a symbolic link pointing to a file/folder, change the target of the link to another file/folder.
    Ensure that the old file is being monitored and the new one is not before symlink_checker runs.
    Wait until symlink_checker runs and ensure that the new file is being monitored and the old one is not.

    Args:
        tags_to_apply (set): Run test if matches with a configuration identifier, skip otherwise.
        main_folder (str): Directory that is being pointed at or contains the pointed file.
        aux_folder (str): Directory that will be pointed at or will contain the future pointed file.
        get_configuration (fixture): Gets the current configuration of the test.
        configure_environment (fixture): Configure the environment for the execution of the test.
        restart_syscheckd (fixture): Restarts syscheck.
        wait_for_fim_start (fixture): Waits until the first FIM scan is completed.

    Raises:
        TimeoutError: If a expected event wasn't triggered.
        AttributeError: If a unexpected event was captured.
    """

    def modify_and_check_events(f1, f2, text):
        """
        Modify the content of 2 given files. We assume the first one is being monitored and the other one is not.
        We expect a 'modified' event for the first one and a timeout for the second one.
        """
        fim.modify_file_content(f1, file1, text)
        fim.modify_file_content(f2, file1, text)
        fim.check_time_travel(scheduled, monitor=wazuh_log_monitor)
        modify = wazuh_log_monitor.start(timeout=3, callback=fim.callback_detect_event,
                                         error_message='Did not receive expected "Sending FIM event: ..." event'
                                         ).result()
        assert 'modified' in modify['data']['type'] and f1 in modify['data']['path'], \
            f"'modified' event not matching for {file1}"
        with pytest.raises(TimeoutError):
            event = wazuh_log_monitor.start(timeout=3, callback=fim.callback_detect_event)
            logger.error(f'Unexpected event {event.result()}')
            raise AttributeError(f'Unexpected event {event.result()}')

    check_apply_test(tags_to_apply, get_configuration['tags'])
    scheduled = get_configuration['metadata']['fim_mode'] == 'scheduled'
    whodata = get_configuration['metadata']['fim_mode'] == 'whodata'
    file1 = 'regular1'

    # If symlink is pointing to a directory, we need to add files and expect their 'added' event (only if the file
    # is being created withing the pointed directory
    if main_folder == testdir_target:
        fim.create_file(fim.REGULAR, main_folder, file1, content='')
        fim.create_file(fim.REGULAR, aux_folder, file1, content='')
        fim.check_time_travel(scheduled, monitor=wazuh_log_monitor)
        add = wazuh_log_monitor.start(timeout=3, callback=fim.callback_detect_event,
                                      error_message='Did not receive expected "Sending FIM event: ..." event'
                                      ).result()
        assert 'added' in add['data']['type'] and file1 in add['data']['path'], \
            f"'added' event not matching for {file1}"
        with pytest.raises(TimeoutError):
            event = wazuh_log_monitor.start(timeout=3, callback=fim.callback_detect_event)
            logger.error(f'Unexpected event {event.result()}')
            raise AttributeError(f'Unexpected event {event.result()}')
    else:
        fim.create_file(fim.REGULAR, aux_folder, file1, content='')
        with pytest.raises(TimeoutError):
            event = wazuh_log_monitor.start(timeout=3, callback=fim.callback_detect_event)
            logger.error(f'Unexpected event {event.result()}')
            raise AttributeError(f'Unexpected event {event.result()}')

    # Change the target of the symlink and expect events while there's no syscheck scan
    # Don't expect events from the new target
    if tags_to_apply == {'monitored_dir'}:
        modify_symlink(aux_folder, os.path.join(testdir_link, 'symlink2'))
    else:
        modify_symlink(aux_folder, os.path.join(testdir_link, 'symlink'), file=file1)
    modify_and_check_events(main_folder, aux_folder, 'Sample number one')

    wait_for_symlink_check(wazuh_log_monitor)
    fim.wait_for_audit(whodata, wazuh_log_monitor)

    # Expect events the other way around now
    modify_and_check_events(aux_folder, main_folder, 'Sample number two')
