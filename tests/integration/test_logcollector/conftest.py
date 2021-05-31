# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import pytest
import wazuh_testing.tools.configuration as conf
from wazuh_testing.logcollector import LOGCOLLECTOR_DEFAULT_LOCAL_INTERNAL_OPTIONS
from wazuh_testing.tools import LOG_FILE_PATH
from wazuh_testing.tools.file import truncate_file
from wazuh_testing.tools.monitoring import FileMonitor
from wazuh_testing.tools.services import control_service

DAEMON_NAME = "wazuh-logcollector"


@pytest.fixture(scope='module')
def restart_logcollector(get_configuration, request):
    """Reset log file and start a new monitor."""
    control_service('stop', daemon=DAEMON_NAME)
    truncate_file(LOG_FILE_PATH)
    file_monitor = FileMonitor(LOG_FILE_PATH)
    setattr(request.module, 'wazuh_log_monitor', file_monitor)
    control_service('start', daemon=DAEMON_NAME)


@pytest.fixture(scope="package", autouse=True)
def configure_local_internal_options_logcollector():
    """Configure Wazuh with local internal options required for logcollector tests."""
    backup_options_lines = conf.get_wazuh_local_internal_options()
    backup_options_dict = conf.local_internal_options_to_dict(backup_options_lines)

    if backup_options_dict != LOGCOLLECTOR_DEFAULT_LOCAL_INTERNAL_OPTIONS:
        conf.add_wazuh_local_internal_options(LOGCOLLECTOR_DEFAULT_LOCAL_INTERNAL_OPTIONS)

        control_service('restart')

        yield

        conf.set_wazuh_local_internal_options(backup_options_lines)

        control_service('restart')
    else:
        yield
