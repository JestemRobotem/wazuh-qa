# Copyright (C) 2015-2022, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os
import time
import pytest

from common import register_agent
from system import (check_agent_groups, check_agent_status, restart_cluster, clean_cluster_logs,
                    check_keys_file, assign_agent_to_new_group, delete_group_of_agents, remove_cluster_agents)
                    
from wazuh_testing.tools.system import HostManager



# Hosts
test_infra_managers = ["wazuh-master", "wazuh-worker1", "wazuh-worker2"]
test_infra_agents = ["wazuh-agent1"]

inventory_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              'provisioning', 'enrollment_cluster', 'inventory.yml')
host_manager = HostManager(inventory_path)
local_path = os.path.dirname(os.path.abspath(__file__))
tmp_path = os.path.join(local_path, 'tmp')


@pytest.fixture(scope='function')
def clean_environment():

    clean_cluster_logs(test_infra_agents + test_infra_managers, host_manager)

    yield
    # Remove the agent once the test has finished
    remove_cluster_agents(test_infra_managers[0], test_infra_agents, host_manager)


@pytest.mark.parametrize("initial_status", ['active', 'disconnected'])
@pytest.mark.parametrize("agent_target", ["wazuh-master", "wazuh-worker1"])
def test_assign_agent_to_a_group(agent_target, initial_status, clean_environment):
    '''
    description: Check agent enrollment process and new group assignment works as expected in a cluster environment.
                 Check that when an agent pointing to a master/worker node is registered using CLI tool, and when
                 it's assigned to a new group the change is sync with the cluster.
    wazuh_min_version: 4.4.0
    parameters:
        - agent_target:
            type: string
            brief: name of the host where the agent will register
        - initial_status:
            type: string
            brief: status of the agent when the assign the new group
        - clean_enviroment:
            type: fixture
            brief: Reset the wazuh log files at the start of the test. Remove all registered agents from master.
    assertions:
        - Verify that after registering the agent key file exists in all nodes.
        - Verify that after registering and before starting the agent, it has no groups assigned.
        - Verify that after registering the agent appears as active/disconnected in all nodes.
        - Verify that after registering and after starting the agent, it has the 'group_test' group assigned.
    expected_output:
        - The agent 'Agent_name' with ID 'Agent_id' belongs to groups: group_test."
    '''
    agent_ip, agent_id, agent_name, manager_ip = register_agent(test_infra_agents[0], agent_target, host_manager)
    # Check that agent has no group assigned
    check_agent_groups(agent_id, 'Null', test_infra_managers, host_manager)

    # Check that agent has client key file
    assert check_keys_file(test_infra_agents[0], host_manager)

    # Start the enrollment process by restarting cluster
    restart_cluster(test_infra_agents, host_manager)

    time.sleep(10)
    # Check that agent status is active in cluster
    check_agent_status(agent_id, agent_name, agent_ip, 'active', host_manager, test_infra_managers)

    if (initial_status == 'disconnected'):
        host_manager.control_service(host='wazuh-agent1', service='wazuh', state="stopped")
        time.sleep(10)
        check_agent_status(agent_id, agent_name, agent_ip, 'disconnected', host_manager, test_infra_managers)

    try:
        # Add agent to a new group
        assign_agent_to_new_group('wazuh-master', 'group_test', agent_id, host_manager)

        time.sleep(10)
        # Check that agent has group set to group_test on Managers
        check_agent_groups(agent_id, 'group_test', test_infra_managers, host_manager)

    finally:
        # Delete group of agent
        delete_group_of_agents('wazuh-master', 'group_test', host_manager)
