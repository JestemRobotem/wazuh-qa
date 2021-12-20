# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import json
import pytest
import os

from wazuh_testing.tools.file import validate_json_file, read_json_file
from wazuh_testing.tools.file import write_json_file
from wazuh_testing.tools.file import recursive_directory_creation


@pytest.fixture
def get_first_result(request):
    """Allow to use the --before-file parameter in order to pass the results
    before upgrade Wazuh.

    Args:
        request (fixture): Provide information on the executing test function.
    """
    return request.config.getoption('--before-results')


@pytest.fixture
def get_second_result(request):
    """Allow to use the --after-file parameter in order to pass the results
    after upgrade Wazuh.

    Args:
        request (fixture): Provide information on the executing test function.
    """
    return request.config.getoption('--after-results')


@pytest.fixture
def get_output_path(request):
    """Allow to use the --output-path parameter to store the test result in the
    specified file.

    Args:
        request (fixture): Provide information on the executing test function.
    """
    return request.config.getoption('--output-path')


@pytest.fixture
def get_ingestion_rate(request):
    """Allow to use the --ingestion-rate parameter.

    Args:
        request (fixture): Provide information on the executing test function.
    """
    return request.config.getoption('--ingestion-rate')


def validate_and_read_json(file_path):
    """Validate the JSON file passed as argument and return its content.

    Args:
        file_path (str): JSON file path.

    Returns:
        The JSON file content.

    Raises:
        ValueError: If the given file is not valid.
    """
    if validate_json_file(file_path):
        file_data = read_json_file(file_path)
    else:
        raise ValueError(f"The file {file_path} is not a valid JSON.")

    return file_data


def test_analysisd_ingestion_rate(get_first_result, get_second_result,
                                  get_output_path):
    """This test checks if the performance of Analysisd decreased after
    upgrade Wazuh.

    Args:
        get_first_result (fixture): Get the results file before making any
        changes to the environment.
        get_second_result (fixture): Get the results file after making any
        changes to the environment.
        get_output_path (fixture): Get the output path where the result will
        be saved.
    """
    file1_data = validate_and_read_json(get_first_result)
    file2_data = validate_and_read_json(get_second_result)
    decoded_1 = int(file1_data['Average']['Decoded'])
    decoded_2 = int(file1_data['Average']['Decoded'])
    dropped_1 = int(file1_data['Average']['Dropped'])
    dropped_2 = int(file2_data['Average']['Dropped'])

    threshold = 70
    decoded_variation = (decoded_2 * 100) / decoded_1
    dropped_variation = (dropped_2 * 100) / dropped_1

    failed = False

    if decoded_2 < decoded_1:
        if decoded_variation < threshold:
            failed = True
    if dropped_2 > dropped_1:
        if (dropped_variation - 100) >= threshold:
            failed = True
    if failed is True:
        assert False, f"The ingestion rate decreased after the upgrade, \
                      check the results within {get_output_path}"

    result_data = {
        'Before the upgrade': file1_data,
        'After the upgrade': file2_data
    }

    recursive_directory_creation(os.path.dirname(get_output_path))
    write_json_file(get_output_path, json.loads(result_data))
