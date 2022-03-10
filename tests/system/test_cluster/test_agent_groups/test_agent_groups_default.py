"""
copyright: Copyright (C) 2015-2022, Wazuh Inc.
           Created by Wazuh, Inc. <info@wazuh.com>.
           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
type: system
brief: Verify that the agent connects correctly to the cluster and that when it has no specific
       configuration, the agent belongs to the default group.
.
tier: 0
modules:
    - cluster
components:
    - manager
    - agent
path: /tests/system/test_cluster/test_agent_groups/test_agent_groups_default.py
daemons:
    - wazuh-db
    - wazuh-clusterd
os_platform:
    - linux
os_version:
    - Arch Linux
    - Amazon Linux 2
    - Amazon Linux 1
    - CentOS 8
    - CentOS 7
    - CentOS 6
    - Ubuntu Focal
    - Ubuntu Bionic
    - Ubuntu Xenial
    - Ubuntu Trusty
    - Debian Buster
    - Debian Stretch
    - Debian Jessie
    - Debian Wheezy
    - Red Hat 8
    - Red Hat 7
    - Red Hat 6
references:
    - https://github.com/wazuh/wazuh-qa/issues/2505
tags:
    - cluster
"""
import os
import time
import pytest

from wazuh_testing.tools.system import HostManager
from system import (check_agent_groups, check_agent_status, remove_cluster_agents, restart_cluster, clean_cluster_logs, check_keys_file)
from system.test_cluster.test_agent_groups.common import register_agent

# Hosts
test_infra_managers = ["wazuh-master", "wazuh-worker1", "wazuh-worker2"]
test_infra_agents = ["wazuh-agent1"]

inventory_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              'provisioning', 'enrollment_cluster', 'inventory.yml')
host_manager = HostManager(inventory_path)
local_path = os.path.dirname(os.path.abspath(__file__))
tmp_path = os.path.join(local_path, 'tmp')


@pytest.fixture(scope='function')
def clean_cluster_environment():
    clean_cluster_logs(test_infra_managers + test_infra_agents, host_manager)
    yield
    # Remove the agent once the test has finished
    remove_cluster_agents(test_infra_managers[0], test_infra_agents, host_manager)

@pytest.mark.parametrize("agent_target", test_infra_managers)
def test_agent_default_group(agent_target, clean_cluster_environment):
    '''
    description: Check agent enrollment process and default group assignment works as expected in a cluster enviroment.
    An agent pointing to a master/worker node is registered using cli tool, and it gets assigned the default group
    after it is restarted.
    wazuh_min_version: 4.4.0
    parameters:
        - agent_target:
            type: string
            brief: name of the host where the agent will register
        - clean_cluster_enviroment:
            type: fixture
            brief: Reset the wazuh log files at the start of the test. Remove all registered agents from master.
    assertions:
        - Verify that after registering the agent key file exists in all nodes.
        - Verify that after registering the agent appears as never_connected in all nodes.
        - Verify that after registering and before starting the agent, it has no groups assigned.
        - Verify that after registering the agent appears as active in all nodes.
        - Verify that after registering and after starting the agent, it has the default group assigned.
    expected_output:
        - f"{agent_id}  {agent_name}  {agent_ip}  never_connected"
        - f'{agent_id}  {agent_name}  {agent_ip}  active'
    '''

    agent_ip, agent_id, agent_name, manager_ip = register_agent(test_infra_agents[0],agent_target, host_manager)


    # Check that agent status is never-connected in cluster
    time.sleep(5)
    check_agent_status(agent_id, agent_name, agent_ip, "never_connected", host_manager, test_infra_managers)


    # Check that agent has no group assigned
    check_agent_groups(agent_id, "Null", test_infra_managers, host_manager)

    # Check that agent has client key file
    for host in test_infra_agents + test_infra_managers:
        assert check_keys_file(host, host_manager)

    # Start the enrollment process by restarting cluster
    restart_cluster(test_infra_agents, host_manager)
    time.sleep(10)

    # Check if the agent is active in master and workers
    check_agent_status(agent_id, agent_name, agent_ip, "active", host_manager, test_infra_managers)

    # Check that agent has group set to default
    check_agent_groups(agent_id, "default", test_infra_managers, host_manager)