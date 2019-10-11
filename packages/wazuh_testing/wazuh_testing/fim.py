# Copyright (C) 2015-2019, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import json
import os
import random
import re
import shutil
import socket
import string
import sys
import time
from collections import Counter
from datetime import timedelta
from stat import ST_ATIME, ST_MTIME, ST_MODE

from jq import jq
from jsonschema import validate

from wazuh_testing.tools import TimeMachine

_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')

WAZUH_PATH = os.path.join('/', 'var', 'ossec')
ALERTS_FILE_PATH = os.path.join(WAZUH_PATH, 'logs', 'alerts', 'alerts.json')
WAZUH_CONF_PATH = os.path.join(WAZUH_PATH, 'etc', 'ossec.conf')
LOG_FILE_PATH = os.path.join(WAZUH_PATH, 'logs', 'ossec.log')

FIFO = 'fifo'
SYSLINK = 'sys_link'
SOCKET = 'socket'
REGULAR = 'regular'

CHECK_ALL = 'check_all'
CHECK_SUM = 'check_sum'
CHECK_SHA1SUM = 'check_sha1sum'
CHECK_MD5SUM = 'check_md5sum'
CHECK_SHA256SUM = 'check_sha256sum'
CHECK_SIZE = 'check_size'
CHECK_OWNER = 'check_owner'
CHECK_GROUP = 'check_group'
CHECK_PERM = 'check_perm'
CHECK_ATTRS = 'check_attrs'
CHECK_MTIME = 'check_mtime'
CHECK_INODE = 'check_inode'

REQUIRED_ATTRIBUTES = {
    CHECK_SHA1SUM: 'hash_sha1',
    CHECK_MD5SUM: 'hash_md5',
    CHECK_SHA256SUM: 'hash_sha256',
    CHECK_SIZE: 'size',
    CHECK_OWNER: ['uid', 'user_name'],
    CHECK_GROUP: ['gid', 'group_name'],
    CHECK_PERM: 'perm',
    CHECK_ATTRS: 'win_attributes',
    CHECK_MTIME: 'mtime',
    CHECK_INODE: 'inode',
    CHECK_ALL: {CHECK_SHA256SUM, CHECK_SHA1SUM, CHECK_MD5SUM, CHECK_SIZE, CHECK_OWNER,
                CHECK_GROUP, CHECK_PERM, CHECK_MTIME, CHECK_INODE},
    CHECK_SUM: {CHECK_SHA1SUM, CHECK_SHA256SUM, CHECK_MD5SUM}
}

_REQUIRED_AUDIT = {
    'user_id',
    'user_name',
    'group_id',
    'group_name',
    'process_name',
    'path',
    'audit_uid',
    'audit_name',
    'effective_uid',
    'effective_name',
    'ppid',
    'process_id'  # Only in windows, TODO parametrization
}

_last_log_line = 0


def load_fim_alerts(n_last=0):
    with open(ALERTS_FILE_PATH, 'r') as f:
        alerts = f.read()
    return list(filter(lambda x: x is not None, jq('.syscheck').transform(text=alerts, multiple_output=True)))[-n_last:]


def validate_event(event, checks=None):
    """ Checks if event is properly formatted according to some checks.

    :param event: dict representing an event generated by syscheckd
    :param checks: set of xml CHECK_* options. Default {CHECK_ALL}.

    :return: None
    """

    def get_required_attributes(check_attributes, result=None):
        result = set() if result is None else result
        for check in check_attributes:
            mapped = REQUIRED_ATTRIBUTES[check]
            if isinstance(mapped, str):
                result |= {mapped}
            elif isinstance(mapped, list):
                result |= set(mapped)
            elif isinstance(mapped, set):
                result |= get_required_attributes(mapped, result=result)
        return result

    checks = {CHECK_ALL} if checks is None else checks
    with open(os.path.join(_data_path, 'syscheck_event.json'), 'r') as f:
        schema = json.load(f)
    validate(schema=schema, instance=event)

    # Check attributes
    attributes = event['data']['attributes'].keys() - {'type', 'checksum'}
    required_attributes = get_required_attributes(checks)
    assert (attributes ^ required_attributes == set())

    # Check audit
    if event['data']['mode'] == 'whodata':
        assert ('audit' in event['data'])
        assert (event['data']['audit'].keys() ^ _REQUIRED_AUDIT == set())


def is_fim_scan_ended():
    message = 'File integrity monitoring scan ended.'
    line_number = 0
    with open(LOG_FILE_PATH, 'r') as f:
        for line in f:
            line_number += 1
            if line_number > _last_log_line:  # Ignore if has not reached from_line
                if message in line:
                    globals()['_last_log_line'] = line_number
                    return line_number
    return -1


def _is_binary(content):
    is_binary = re.compile('^b\'.*\'$')
    return is_binary.match(str(content))


def create_file(type, path, name, content=''):
    """ Creates a file in a given path. The path will be created in case it does not exists.

    :param type: Defined constant that specifies the type. It can be: FIFO, SYSLINK, SOCKET or REGULAR
    :type type: Constant string
    :param path: Path where the file will be created
    :type path: String
    :param name: File name
    :type name: String
    :param content: Content of the file. Used for regular files.
    :type content: String or binary
    :return: None
    """
    os.makedirs(path, exist_ok=True)
    getattr(sys.modules[__name__], f'_create_{type}')(path, name, content)


def _create_fifo(path, name, content):
    """ Creates a FIFO file.

    :param path: Path where the file will be created
    :type path: String
    :param name: File name
    :type name: String
    :param content: Content of the created file
    :type content: String or binary
    :return: None
    """
    fifo_path = os.path.join(path, name)
    try:
        os.mkfifo(fifo_path)
    except OSError:
        raise


def _create_sys_link(path, name, content):
    """ Creates a SysLink file.

    :param path: Path where the file will be created
    :type path: String
    :param name: File name
    :type name: String
    :param content: Content of the created file
    :type content: String or binary
    :return: None
    """
    syslink_path = os.path.join(path, name)
    try:
        os.symlink(syslink_path, syslink_path)
    except OSError:
        raise


def _create_socket(path, name, content):
    """ Creates a Socket file.

    :param path: Path where the file will be created
    :type path: String
    :param name: File name
    :type name: String
    :param content: Content of the created file
    :type content: String or binary
    :return: None
    """
    socket_path = os.path.join(path, name)
    try:
        os.unlink(socket_path)
    except OSError:
        if os.path.exists(socket_path):
            raise
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(socket_path)


def _create_regular(path, name, content):
    """ Creates a Regular file.

    :param path: Path where the file will be created
    :type path: String
    :param name: File name
    :type name: String
    :param content: Content of the created file
    :type content: String or binary
    :return: None
    """
    regular_path = os.path.join(path, name)
    mode = 'wb' if _is_binary(content) else 'w'

    with open(regular_path, mode) as f:
        f.write(content)


def delete_file(path, name):
    """ Deletes regular file """
    regular_path = os.path.join(path, name)
    if os.path.exists(regular_path):
        os.remove(regular_path)


def modify_file(path, name, is_binary=False, options=None):
    """ Modify a Regular file.

    :param path: Path where the file will be created
    :type path: String
    :param name: File name
    :type name: String
    :param is_binary: True if the file is binary. False otherwise.
    :type is_binary: boolean
    :param options: Dict with all the checkers 
    :type options: Dict
    :return: None
    """
    def modify_file_content():
        if is_binary:
            content = b"1234567890qwertyuiopasdfghjklzxcvbnm"
            mode = 'ab'
        else:
            content = "1234567890qwertyuiopasdfghjklzxcvbnm"
            mode = 'a'

        with open(regular_path, mode) as f:
            f.write(content)

    def modify_file_mtime():
        stat = os.stat(regular_path)
        access_time = stat[ST_ATIME]
        modification_time = stat[ST_MTIME]
        modification_time = modification_time + (120)
        os.utime(regular_path, (access_time, modification_time))

    def modify_file_owner():
        os.chown(regular_path, 1, -1)

    def modify_file_group():
        os.chown(regular_path, -1, 1)

    def modify_file_permission():
        os.chmod(regular_path, 0o666)

    def modify_file_inode():
        shutil.copyfile(regular_path, os.path.join(path, "inodetmp"))
        os.replace(os.path.join(path, "inodetmp"), regular_path)


    regular_path = os.path.join(path, name)

    if options is None:
        modify_file_content()
    else:
        for modification_type in options:
            check = REQUIRED_ATTRIBUTES[modification_type]
            if isinstance(check, set):
                modify_file(path, name, check)

            elif isinstance(check, list):
                if check == REQUIRED_ATTRIBUTES[CHECK_OWNER]:
                    modify_file_owner()
                elif check == REQUIRED_ATTRIBUTES[CHECK_GROUP]:
                    modify_file_group()

            else:
                if check == REQUIRED_ATTRIBUTES[CHECK_ALL] or check == CHECK_ALL:
                    modify_file_content()
                    modify_file_mtime()
                    modify_file_owner()
                    modify_file_group()
                    modify_file_permission()
                    modify_file_inode()

                elif (check == REQUIRED_ATTRIBUTES[CHECK_SUM] or check == CHECK_SUM or
                      check == REQUIRED_ATTRIBUTES[CHECK_SHA1SUM] or check == CHECK_SHA1SUM or
                      check == REQUIRED_ATTRIBUTES[CHECK_MD5SUM] or check == CHECK_MD5SUM or
                      check == REQUIRED_ATTRIBUTES[CHECK_SHA256SUM] or check == CHECK_SHA256SUM or
                      check == REQUIRED_ATTRIBUTES[CHECK_SIZE] or check == CHECK_SIZE):
                    modify_file_content()

                elif check == REQUIRED_ATTRIBUTES[CHECK_MTIME] or check == CHECK_MTIME:
                    modify_file_mtime()

                elif check == REQUIRED_ATTRIBUTES[CHECK_OWNER] or check == CHECK_OWNER:
                    modify_file_owner()

                elif check == REQUIRED_ATTRIBUTES[CHECK_GROUP] or check == CHECK_GROUP:
                    modify_file_group()

                elif check == REQUIRED_ATTRIBUTES[CHECK_PERM] or check == CHECK_PERM:
                    modify_file_permission()

                elif check == REQUIRED_ATTRIBUTES[CHECK_INODE] or check == CHECK_INODE:
                    modify_file_inode() 


def change_internal_options(opt_path, pattern, value):
    """ Changes the value of a given parameter

    :param opt_path: File path
    :type opt_path: String
    :type opt_path: String
    :param pattern: Parameter to change
    :type pattern: String
    :param value: New value
    :type value: String
    """
    add_pattern = True
    with open(opt_path, "r") as sources:
        lines = sources.readlines()

    with open(opt_path, "w") as sources:
        for line in lines:
            sources.write(
                re.sub(f'{pattern}=[0-9]*', f'{pattern}={value}', line))
            if pattern in line:
                add_pattern = False

    if add_pattern:
        with open(opt_path, "a") as sources:
            sources.write(f'\n\n{pattern}={value}')


def callback_detect_end_scan(line):
    if 'File integrity monitoring scan ended.' in line:
        return line
    return None


def callback_detect_event(line):
    match = re.match(r'.*Sending event: (.+)$', line)
    if match:
        if json.loads(match.group(1))['type'] == 'event':
            return json.loads(match.group(1))
    return None


def callback_audit_health_check(line):
    if 'Whodata health-check: Success.' in line:
        return True
    return None


def callback_audit_added_rule(line):
    match = re.match(r'.*Added audit rule for monitoring directory: \'(.+)\'', line)
    if match:
        return match.group(1)
    return None


def callback_audit_rules_manipulation(line):
    if 'Detected Audit rules manipulation' in line:
        return True
    return None


def callback_audit_connection(line):
    if '(6030): Audit: connected' in line:
        return True
    return None


def callback_audit_loaded_rule(line):
    match = re.match(r'.*Audit rule loaded: -w (.+) -p', line)
    if match:
        return match.group(1)
    return None


def callback_audit_event_too_long(line):
    if '(6643): Caching Audit message: event too long' in line:
        return True
    return None


def callback_realtime_added_directory(line):
    match = re.match(r'.*Directory added for real time monitoring: \'(.+)\'', line)
    if match:
        return match.group(1)
    return None


def callback_configuration_error(line):
    match = re.match(r'.*CRITICAL: \(\d+\): Configuration error at', line)
    if match:
        return True
    return None


def regular_file_cud(folder, log_monitor, file_list=['testfile0'], time_travel=False, min_timeout=1, options=None,
                     triggers_event=True, validators_after_create=None, validators_after_update=None, 
                     validators_after_delete=None, validators_after_cud=None):
    """ Checks if creation, update and delete events are detected by syscheck

    :param folder: Path where the files will be created
    :type folder: String
    :param log_monitor: File event monitor
    :type log_monitor: FileMonitor
    :param file_list: List/Dict with the file names and content.
    List -> ['name0', 'name1'] -- Dict -> {'name0': 'content0', 'name1': 'content1'}
    If it is a list, it will be transformed to a dict with empty strings in each value.
    :type file_list: Either List or Dict
    :param time_travel: Boolean to determine if there will be time travels or not
    :type time_travel: Boolean
    :param min_timeout: Minimum timeout
    :type min_timeout: Float
    :param options: Dict with all the checkers
    :type options: Dict. Default value is None.
    :param triggers_event: Boolean to determine if the event should be raised or not.
    :type triggers_event: Boolean
    :param validators_after_create: list of functions that validate an event triggered when a new file is created. Each
    function must accept a param to receive the event to be validated.
    :type validators_after_create: list
    :param validators_after_update: list of functions that validate an event triggered when a new file is modified. Each
    function must accept a param to receive the event to be validated.
    :type validators_after_update: list
    :param validators_after_delete: list of functions that validate an event triggered when a new file is deleted. Each
    function must accept a param to receive the event to be validated.
    :type validators_after_delete: list
    :param validators_after_cud: list of functions that validate an event triggered when a new file is created, modified
    or deleted. Each function must accept a param to receive the event to be validated.
    :type validators_after_cud: list
    :return: None
    """

    def check_time_travel():
        if time_travel:
            TimeMachine.travel_to_future(timedelta(hours=13))

    def fetch_events():
        try:
            result = log_monitor.start(timeout=max(len(file_list) * 0.01, min_timeout),
                                       callback=callback_detect_event,
                                       accum_results=len(file_list)
                                       ).result()
            return result if isinstance(result, list) else [result]
        except TimeoutError:
            if triggers_event:
                raise

    def validate_checkers_per_event():
        if options is not None:
            for ev in events:
                validate_event(ev, options)

    def check_events_type(ev_type):
        event_types = Counter(jq(".[].data.type").transform(events, multiple_output=True))
        assert (event_types[ev_type] == len(file_list))

    def check_files_in_event():
        file_paths = jq(".[].data.path").transform(events, multiple_output=True)
        for file_name in file_list:
            assert (os.path.join(folder, file_name) in file_paths)

    def check_events(event_type, validate_after):
        if events is not None:
            validate_checkers_per_event()
            check_events_type(event_type)
            check_files_in_event()
            run_custom_validators(validators_after_cud)
            run_custom_validators(validate_after)

    def run_custom_validators(validators):
        if validators is not None:
            for validator in validators:
                for event in events:
                    validator(event)

    # Transform file list
    if not isinstance(file_list, list) and not isinstance(file_list, dict):
        raise ValueError('Value error. It can only be list or dict')
    elif isinstance(file_list, list):
        file_list = {i: '' for i in file_list}

    # Create text files
    for name, content in file_list.items():
        create_file(REGULAR, folder, name, content)

    check_time_travel()
    events = fetch_events()
    check_events('added', validators_after_create)

    # Modify previous text files
    for name, content in file_list.items():
        modify_file(folder, name, is_binary=_is_binary(content), options=options)

    check_time_travel()
    events = fetch_events()
    check_events('modified', validators_after_update)

    # Delete previous text files
    for name in file_list:
        delete_file(folder, name)

    check_time_travel()
    events = fetch_events()
    check_events('deleted', validators_after_delete)


def detect_initial_scan(file_monitor):
    """ Detect initial scan when restarting Wazuh

    :param file_monitor: Wazuh log monitor to detect syscheck events
    :type file_monitor: FileMonitor
    :return: None
    """
    file_monitor.start(timeout=60, callback=callback_detect_end_scan)
    # Add additional sleep to avoid changing system clock issues (TO BE REMOVED when syscheck has not sleeps anymore)
    time.sleep(11)
