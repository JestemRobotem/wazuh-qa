# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os
import shutil

from wazuh_testing.qa_docs import QADOCS_LOGGER
from wazuh_testing.tools.logging import Logging

utils_logger = Logging.get_logger(QADOCS_LOGGER)


def check_existance(source, key):
    """Check recursively if a key exists into a dictionary.

    Args:
        source (dict): The source dictionary where the key should be found.
        key (str): A string with the name of the key to look into the source dictionary.

    Returns:
        boolean: A boolean with True if it exists. False otherwise.
    """
    if not isinstance(source, dict) and not isinstance(source, list):
        return False

    if key in source:
        return True

    elif isinstance(source, dict):
        for item in source:
            if check_existance(source[item], key):
                return True

        return False

    elif isinstance(source, list):
        for item in source:
            if check_existance(item, key):
                return True

        return False

    else:
        return False


def remove_inexistent(source, check_list, stop_list=None):
    """Check recursively if a source dictionary contains invalid keys that must be deleted.

    Args:
        source (dict): The source dictionary where the key should be found.
        check_list (dict): A dictionary with all the valid keys.
        stop_list (list): A list with the keys that ends the recursivity.
    """
    for element in list(source):
        if stop_list and element in stop_list:
            break

        if not check_existance(check_list, element):
            del source[element]
        elif isinstance(source[element], dict):
            remove_inexistent(source[element], check_list, stop_list)


def get_keys_dict(_dic):
    """Flat a dictionary into a list of its keys.

    Args:
        _dic (dict): The source dictionary to be flattened."

    Returns:
        keys (list): A list of flattened keys. If there is only a key, that one is returned.
    """
    keys = []

    for item in _dic:
        value = _dic[item]

        if isinstance(value, dict):
            result = get_keys_dict(value)
            keys.append({item: result})

        elif isinstance(value, list):
            result = get_keys_list(value)
            keys.append({item: result})

        else:
            keys.append(item)

    if len(keys) == 1:
        return keys[0]
    else:
        return keys


def get_keys_list(_list):
    """Flat a list of dictionaries into a list of its keys.

    Args:
        _list (list): The source list to be flattened.

    Returns:
        keys (list): A list of flattened keys. If there is only a key, that one is returned.
    """
    keys = []

    for item in _list:
        if isinstance(item, dict):
            result = get_keys_dict(item)
            keys.append(result)

        elif isinstance(item, list):
            result = get_keys_list(item)
            keys.append(result)

        else:
            keys.append(item)

    if len(keys) == 1:
        return keys[0]
    else:
        return keys


def find_item(search_item, check):
    """Search for a specific key into a list of dictionaries or values.

    Args:
        search_item (str): A string that contains the key to be found.
        check (list): A list of dictionaries or values where the key should be found.

    Returns:
        item (str): The value of the finding. None if the key could not be found.
"""
    for item in check:
        if isinstance(item, dict):
            list_element = list(item.keys())
            if search_item == list_element[0]:
                return list(item.values())[0]
        else:
            if search_item == item:
                return item

    return None


def check_missing_field(source, check):
    """Check recursively if a source dictionary contains all the expected keys.

    Args:
        source (dict): The source dictionary where the key should be found.
        check (list): A list with the expected keys.

    Returns:
        str: If not found, the missing key is returned. None otherwise.
    """
    missing_filed = None

    for source_field in source:
        if isinstance(source_field, dict):
            key = list(source_field.keys())[0]
            found_item = find_item(key, check)

            if not found_item:
                utils_logger.warning(f"Missing key {source_field}")
                return key

            missing_filed = check_missing_field(source_field[key], found_item)

            if missing_filed:
                return missing_filed

        elif isinstance(source_field, list):
            missing_filed = None

            for check_element in check:
                missing_filed = check_missing_field(source_field, check_element)
                if not missing_filed:
                    break

            if missing_filed:
                return source_field
        else:
            found_item = find_item(source_field, check)

            if not found_item:
                utils_logger.warning(f"Missing key {source_field}")
                return source_field

    return missing_filed


def clean_folder(folder):
    """Completely clean the content of a folder.

    Args:
        folder (str): A string with the path of the folder to be cleaned.
    """
    if not os.path.exists(folder):
        return

    utils_logger.debug(f"Going to clean '{folder}' folder")

    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)

        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            utils_logger.error(f"Failed to delete {file_path}. Reason: {e}")
