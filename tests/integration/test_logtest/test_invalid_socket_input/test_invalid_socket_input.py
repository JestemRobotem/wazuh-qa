# Copyright (C) 2015-2020, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os

import pytest
import yaml
from string import ascii_uppercase
import random

from wazuh_testing import global_parameters
from wazuh_testing.analysis import callback_fim_error
from wazuh_testing.tools import LOG_FILE_PATH, WAZUH_PATH

# Marks

pytestmark = [pytest.mark.linux, pytest.mark.tier(level=0), pytest.mark.server]

# Configurations

test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
messages_path = os.path.join(test_data_path, 'invalid_socket_input.yaml')
with open(messages_path) as f:
    test_cases = yaml.safe_load(f)

# Variables

log_monitor_paths = [LOG_FILE_PATH]
logtest_path = os.path.join(os.path.join(WAZUH_PATH, 'queue', 'ossec', 'logtest'))

receiver_sockets_params = [(logtest_path, 'AF_UNIX', 'TCP')]

receiver_sockets, monitored_sockets, log_monitors = None, None, None  # Set in the fixtures


# Tests

@pytest.mark.parametrize('test_case',
                         [test_case['test_case'] for test_case in test_cases],
                         ids=[test_case['name'] for test_case in test_cases])
def test_invalid_socket_input(connect_to_sockets_function, test_case: list):
    """Check that every input message in logtest socket generates the adequate output

    Parameters
    ----------
    test_case : list
        List of test_case stages (dicts with input, output and stage keys)
    """
    stage = test_case[0]

    if stage["stage"] != 'Oversize message':
        receiver_sockets[0].send(stage['input'], size=True)
    else:
        over_size_parameter = ''.join(random.choice(ascii_uppercase) for _ in range(2 ** 16))
        receiver_sockets[0].send(stage['input'].format(over_size_parameter), size=True)

    result = receiver_sockets[0].receive(size=True).rstrip(b'\x00').decode()
    assert stage['output'] == result, 'Failed test case stage {}: {}'.format(test_case.index(stage) + 1,
                                                                             stage['stage'])
