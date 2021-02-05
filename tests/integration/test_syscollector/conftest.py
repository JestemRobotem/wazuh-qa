# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import pytest
import time
from subprocess import CalledProcessError

from wazuh_testing.tools import LOG_FILE_PATH
from wazuh_testing.tools.file import truncate_file
from wazuh_testing.tools.monitoring import FileMonitor
from wazuh_testing.tools.services import control_service


@pytest.fixture(scope='module')
def restart_modulesd(get_configuration, request):
    # Reset ossec.log and start a new monitor
    control_service('stop', daemon='wazuh-modulesd')
    time.sleep(2.4)
    truncate_file(LOG_FILE_PATH)
    file_monitor = FileMonitor(LOG_FILE_PATH)
    setattr(request.module, 'wazuh_log_monitor', file_monitor)
    try:
        control_service('start', daemon='wazuh-modulesd')
    except ValueError:
        pass

@pytest.fixture
def restart_modulesd_catching_ossec_conf_error(request):
    control_service('stop', daemon='wazuh-modulesd')
    time.sleep(2.4)
    truncate_file(LOG_FILE_PATH)
    file_monitor = FileMonitor(LOG_FILE_PATH)
    setattr(request.module, 'wazuh_log_monitor', file_monitor)
    try:
        control_service('start', daemon='wazuh-modulesd')
    except (ValueError, CalledProcessError):
        pass
