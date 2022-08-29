# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
import os
import shutil
from typing import List
import pytest

from wazuh_testing.tools.services import control_service
from wazuh_testing.tools import configuration, ARCHIVES_LOG_FILE_PATH, \
                                ALERT_LOGS_PATH, ALERT_FILE_PATH, ALERT_DIRECTORY, WAZUH_INTERNAL_OPTIONS
from wazuh_testing.modules.eps import simulate_agent_function, syslog_simulator_function


@pytest.fixture(scope='function')
def restart_analysisd_function():
    """Restart wazuh-analysisd daemon before starting a test, and stop it after finishing"""
    control_service('restart', daemon='wazuh-analysisd')
    yield
    control_service('stop', daemon='wazuh-analysisd')


@pytest.fixture(scope='module')
def configure_local_internal_options_eps(request):
    """Fixture to configure the local internal options file."""
    # Define local internal options for EPS tests
    local_internal_options = {'wazuh_modules.debug': '2', 'monitord.rotate_log': '0',
                              'analysisd.state_interval': f"{request.param[0]}"}

    # Backup the old local internal options
    backup_local_internal_options = configuration.get_wazuh_local_internal_options()

    # Set the new local internal options configuration
    configuration.set_wazuh_local_internal_options(configuration.create_local_internal_options(local_internal_options))

    yield

    # Backup the old local internal options cofiguration
    configuration.set_wazuh_local_internal_options(backup_local_internal_options)


@pytest.fixture(scope='function')
def set_wazuh_configuration_eps(configuration, set_wazuh_configuration, configure_local_internal_options_eps):
    """Set wazuh configuration

    Args:
        configuration (dict): Configuration template data to write in the ossec.conf.
        set_wazuh_configuration (fixture): Set the wazuh configuration according to the configuration data.
        configure_local_internal_options_eps (fixture): Set the local_internal_options.conf file.
    """
    yield


@pytest.fixture(scope='function')
def simulate_agent(request):
    """Fixture to run the script simulate_agent.py"""
    simulate_agent_function(request.param)

    yield


def delete_folder_content(folder):
    """Delete alerts folder content execution"""
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        try:
            shutil.rmtree(filepath)
        except OSError:
            os.remove(filepath)


@pytest.fixture(scope='function')
def delete_alerts_folder():
    """Delete alerts folder content before and after execution"""

    delete_folder_content(ALERT_DIRECTORY)

    yield

    delete_folder_content(ALERT_DIRECTORY)


@pytest.fixture(scope='function')
def configure_wazuh_one_thread():
    """Fixture to configure the local internal options file to work with one thread."""
    local_internal_options = {'analysisd.event_threads': '1', 'analysisd.syscheck_threads': '1',
                              'analysisd.syscollector_threads': '1', 'analysisd.rootcheck_threads': '1',
                              'analysisd.sca_threads': '1', 'analysisd.hostinfo_threads': '1',
                              'analysisd.winevt_threads': '1', 'analysisd.rule_matching_threads': '1',
                              'analysisd.dbsync_threads': '1', 'remoted.worker_pool': '1'}

    # Backup the old local internal options
    backup_local_internal_options = configuration.get_wazuh_local_internal_options()

    # Add the new configuration to local internal options
    configuration.add_wazuh_local_internal_options(local_internal_options)

    yield

    # Backup the old local internal options cofiguration
    configuration.set_wazuh_local_internal_options(backup_local_internal_options)


@pytest.fixture(scope='session')
def load_wazuh_basic_configuration():
    """Load a new basic ocnfiguration to the manager"""
    # Reference paths
    DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
    CONFIGURATIONS_PATH = os.path.join(DATA_PATH, 'wazuh_basic_configuration')
    configurations_path = os.path.join(CONFIGURATIONS_PATH, 'ossec.conf')

    backup_ossec_configuration = configuration.get_wazuh_conf()

    with open(configurations_path, 'r') as file:
        lines = file.readlines()
    configuration.write_wazuh_conf(lines)

    yield

    configuration.write_wazuh_conf(backup_ossec_configuration)


@pytest.fixture(scope='module')
def load_local_rules():
    """Load local rules to override original rules"""
    # Reference paths
    DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
    CONFIGURATIONS_PATH = os.path.join(DATA_PATH, 'wazuh_rules')
    configurations_path = os.path.join(CONFIGURATIONS_PATH, 'local_rules.xml')

    backup_local_rules = configuration.get_wazuh_local_rules()

    with open(configurations_path, 'r') as file:
        lines = file.readlines()
    configuration.write_wazuh_local_rules(lines)

    yield

    configuration.write_wazuh_local_rules(backup_local_rules)


@pytest.fixture(scope='function')
def syslog_simulator(request):
    """Fixture to run the script syslog_simulator.py"""
    syslog_simulator_function(request.param)

    yield
