# Needs installed in system: sysstat, bc

import os
import re
import time
from enum import Enum
from multiprocessing import Process, Manager
from random import randrange
from socket import socket, AF_UNIX, SOCK_STREAM
from struct import pack, unpack

import pytest

from wazuh_testing.tools import WAZUH_PATH, ALERT_FILE_PATH
from wazuh_testing.tools.file import truncate_file
from wazuh_testing.tools.monitoring import FileMonitor

agent_conf = os.path.join(WAZUH_PATH, 'etc', 'shared', 'default', 'agent.conf')
state_path = os.path.join(WAZUH_PATH, 'var', 'run')
db_path = '/var/ossec/queue/db/wdb'
manager_ip = '172.19.0.100'
setup_environment_time = 1  # Seconds
state_collector_time = 5  # Seconds
max_time_for_agent_setup = 180  # Seconds
tested_daemons = ["wazuh-db", "ossec-analysisd", "ossec-remoted"]


class Cases(Enum):
    case0 = 0  # Database empty
    case1 = 1  # Change one random checksum in fim_entry table
    case2 = 2  # Change all checksums in fim_entry table


def db_query(agent, query):
    """ Run a query against wazuh_db for a specific agent

    Parameters
    ----------
    agent : str
        Database identifier
    query : str
        Query to be executed

    Returns
    -------
    str
        Return the wazuh-db's socket response

    """
    sock = socket(AF_UNIX, SOCK_STREAM)
    sock.connect(db_path)

    msg = f'agent {agent} sql {query}'.encode()
    sock.send(pack(f"<I{len(msg)}s", len(msg), msg))

    length = unpack("<I", sock.recv(4))[0]
    return sock.recv(length).decode(errors='ignore')


def get_total_disk_info(daemon):
    """ Get total disk read/write info from /proc/[pid]/io

    Parameters
    ----------
    daemon : str
        Daemon for whom we will get the stats.

    Returns
    -------
    tuple of str
        Total read value and total write value

    """
    regex_write = r"write_bytes: ([0-9]+)"
    regex_read = r"read_bytes: ([0-9]+)"
    pid = os.popen('pidof ' + daemon).read().strip()

    with open(os.path.join(f'/proc/{pid}/io'), 'r') as io_info:
        info = io_info.read()
        total_read = float(re.search(regex_read, info).group(1)) / 1024  # KB
        total_write = float(re.search(regex_write, info).group(1)) / 1024  # KB

    return (str(total_read), str(total_write))


def get_stats(daemon):
    """ Get CPU, RAM, disk read and disk write stats using ps and pidstat

    Parameters
    ----------
    daemon : str
        Daemon for whom we will get the stats.

    Returns
    -------
    list of str
        Return CPU, RAM, Disk reading, Disk writing, Total disk reading, total disk writing

    """
    regex_cpu = rf"{daemon} *([0-9]+.[0-9]+) *[0-9]+"
    regex_mem = rf"{daemon} *[0-9]+.[0-9]+ *([0-9]+)"
    regex_disk_rd_wr = rf".* *[0-9]* *[0-9]* *([0-9]+.[0-9]+) *([0-9]+.[0-9]+) *[0-9]+.[0-9]+ *{daemon}"
    # char 37 is %
    ps = os.popen(f'ps -axo comm,%cpu,rss | grep \"{daemon}\" | head -n1').read()
    pidstat = os.popen(f'pidstat -d | grep {daemon} | head -n1').read()
    try:
        cpu, mem = re.match(regex_cpu, ps).group(1), re.match(regex_mem, ps).group(1)
        disk_rd, disk_wr = re.match(regex_disk_rd_wr, pidstat).group(1), re.match(regex_disk_rd_wr, pidstat).group(2)
        total_disk_info = get_total_disk_info(daemon)

        return [cpu, mem, disk_rd, disk_wr, total_disk_info[0], total_disk_info[1]]
    except AttributeError:
        pass


def n_attempts(agent):
    """ Return n_attempts in sync_info table

    Parameters
    ----------
    agent : str
        Check the number of attempts for this agent

    Returns
    -------
    int
        Return the number of attempts for the specified agent

    """
    regex = r"ok \[{\"n_attempts\":([0-9]+)}\]"
    response = db_query(agent, 'SELECT n_attempts FROM sync_info')

    try:
        return int(re.match(regex, response).group(1))
    except AttributeError:
        raise AttributeError('[ERROR] Database locked!')


def n_completions(agent):
    """ Return n_completions in sync_info table

    Parameters
    ----------
    agent : str
        Check the number of completions for this agent

    Returns
    -------
    int
        Return the number of completions for the specified agent

    """
    regex = r"ok \[{\"n_completions\":([0-9]+)}\]"
    response = db_query(agent, 'SELECT n_completions FROM sync_info')

    try:
        return int(re.match(regex, response).group(1))
    except AttributeError:
        raise AttributeError('[ERROR] Database locked!')


def get_agents(client_keys='/var/ossec/etc/client.keys'):
    """ These function extract all agent ids in the client.keys file. It will not extract the ids that are removed (!)

    Parameters
    ----------
    client_keys : str
        Path of the client.keys file

    Returns
    -------
    dict
        Dictionary shared by all processes

    """
    agent_regex = r'([0-9]+) [^!.+]+ .+ .+'
    agent_dict = dict()
    agent_ids = list()
    with open(client_keys, 'r') as keys:
        for line in keys.readlines():
            agent_ids.append(re.match(agent_regex, line).group(1))

    for agent_id in agent_ids:
        agent_dict[agent_id.zfill(3)] = Manager().dict({
            'start': 0.0
        })

    return agent_dict


def replace_conf(protocol, eps, directory, buffer):
    """ Function that sets up the configuration for the current test.

    Parameters
    ----------
    protocol : str
        Can be udp or tcp
    eps :
        Events per second
    directory :
        Directory to be monitored
    buffer :
        Can be yes or no, <disabled>yes|no</disabled>

    """
    new_config = str()
    address_regex = r".*<address>([0-9.]+)</address>"
    directory_regex = r'.*<directories check_all=\"yes\">(.+)</directories>'
    eps_regex = r'.*<max_eps>([0-9]+)</max_eps>'
    protocol_regex = r'.*<protocol>([a-z]+)</protocol>'
    buffer_regex = r'<client_buffer><disabled>(yes|no)</disabled></client_buffer>'

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/template_agent.conf'), 'r') as f:
        lines = f.readlines()
        for line in lines:
            line = re.sub(address_regex, '<address>' + manager_ip + '</address>', line)
            line = re.sub(directory_regex, '<directories check_all="yes">' + directory + '</directories>', line)
            line = re.sub(eps_regex, '<max_eps>' + eps + '</max_eps>', line)
            line = re.sub(protocol_regex, '<protocol>' + protocol + '</protocol>', line)
            line = re.sub(buffer_regex, '<client_buffer><disabled>' + buffer + '</disabled></client_buffer>', line)
            new_config += line

        with open(agent_conf, 'w') as conf:
            conf.write(new_config)
    # Set Read/Write permissions to agent.conf
    os.chmod(agent_conf, 0o666)


def check_all_n_attempts(agents_list):
    """ Return max value of n_attempts between all agents

    Parameters
    ----------
    agents_list : list
        List of agent ids

    Returns
    -------
    int
        Maximum number of attempts of the tested agents

    """
    all_n_attempts = list()
    for agent_id in list(agents_list):
        all_n_attempts.append(n_attempts(agent_id))

    return max(all_n_attempts)


def check_all_n_completions(agents_list):
    """ Return min value of n_completions between all agents

    Parameters
    ----------
    agents_list : list
        List of agent ids

    Returns
    -------
    int
        Minimum number of completions of the tested agents

    """
    all_n_completions = list()
    for agent_id in list(agents_list):
        all_n_completions.append(n_completions(agent_id))

    return min(all_n_completions)


def modify_database(agent_id, directory, prefix, total_files, modify_file, modify_all, restore_all):
    """  Modify the database files

    Parameters
    ----------
    agent_id : str
        Database identifier
    directory : str
        Directory of the file to which we will modify your checksum
    prefix : str
        Prefix of the filename
    total_files
        Total files in the directory
    modify_file : bool
        Flag for modify the checksum of a file
    modify_all
        Flag for modify all checksums in the database
    restore_all
        Flag that indicate if all entries in the fim_entry table should be deleted

    """
    if modify_file:
        total_files = int(total_files)
        if total_files == 0:
            total_files = 1
        checksum = 'new_checksum'
        file = f"{directory}/{prefix}{randrange(total_files)}"
        db_query(agent_id, f'UPDATE fim_entry SET checksum="{checksum}" WHERE file="{file}"')
        print(f'[DB] Modify checksum of {file}, set to {checksum}')
    if modify_all:
        checksum = 'new_checksum2'
        db_query(agent_id, f'UPDATE fim_entry SET checksum="{checksum}"')
        print(f'[DB] Modify all checksums to {checksum}')
    if restore_all:
        db_query(agent_id, 'DELETE FROM fim_entry')

    db_query(agent_id, 'UPDATE sync_info SET n_attempts=0')
    db_query(agent_id, 'UPDATE sync_info SET n_completions=0')

    while n_completions(agent_id) != 0 and n_attempts(agent_id) != 0:
        print('[INFO] Waiting for wazuh-db')
        time.sleep(0.1)


def agent_checker(case, agent_id, agents_dict, filename, database_params):
    if case == Cases.case0.value:
        # Detect that the agent are been restarted
        def callback_detect_agent_restart(line):
            try:
                return re.match(rf'.*\"agent\":{{\"id\":\"({agent_id})\".*', line).group(1)
            except (IndexError, AttributeError):
                pass

        FileMonitor(ALERT_FILE_PATH).start(timeout=max_time_for_agent_setup,
                                           callback=callback_detect_agent_restart).result()

    modify_database(agent_id, **database_params)

    while True:
        if n_attempts(agent_id) > 0 and agents_dict[agent_id]['start'] == 0.0:
            agents_dict[agent_id]['start'] = time.time()
            print(f'[AGENT] Agent {agent_id} started at {agents_dict[agent_id]["start"]}')
        if n_completions(agent_id) > 0 and agents_dict[agent_id]['start'] != 0.0:
            info_collector(agents_dict[agent_id], agent_id, filename)
            break


def info_collector(agent, agent_id, filename):
    with open(filename, 'w') as info_agent:
        print(
            f"[AGENT] Info {agent_id} writing: "
            f"{agent_id},{n_attempts(agent_id)},{n_completions(agent_id)},{agent['start']},"
            f"{time.time()},{time.time() - agent['start']}")
        info_agent.write("agent_id,n_attempts,n_completions,start_time,end_time,total_time\n")
        info_agent.write(f"{agent_id},{n_attempts(agent_id)},{n_completions(agent_id)},{agent['start']},"
                         f"{time.time()},{time.time() - agent['start']}\n")


def state_collector(case, protocol, eps, files, agents_dict, buffer):
    daemons_dict = {
        'ossec-analysisd': {
            'headers': ['syscheck_events_decoded', 'syscheck_edps', 'dbsync_queue_usage',
                        'dbsync_messages_dispatched', 'dbsync_mdps', 'events_received', 'events_dropped',
                        'syscheck_queue_usage', 'event_queue_usage'],
            'deleted': False,
            'no_headers': True},
        'ossec-remoted': {
            'headers': ['queue_size', 'tcp_sessions', 'evt_count', 'discarded_count', 'recv_bytes'],
            'deleted': False,
            'no_headers': True
        }
    }

    while True:
        if check_all_n_attempts(agents_dict.keys()) > 0:
            for file in os.listdir(state_path):
                if file.endswith('.state'):
                    daemon = str(file.split(".")[0])
                    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            f"stats/state_case{case}-{daemon}_{protocol}_{eps}eps_"
                                            f"{files}files_{buffer}.csv")
                    if not daemons_dict[daemon]['deleted']:
                        try:
                            os.unlink(filename)
                        except FileNotFoundError:
                            pass
                        daemons_dict[daemon]['deleted'] = True
                    with open(filename, 'a') as state:
                        values = list()
                        file_content = open(os.path.join(state_path, file), 'r').read()
                        for field in daemons_dict[daemon]['headers']:
                            values.append(
                                re.search(rf"{field}='([0-9.]+)'", file_content, re.MULTILINE).group(1))
                        if daemons_dict[daemon]['no_headers']:
                            state.write(f"{','.join(daemons_dict[daemon]['headers'])}\n")
                            daemons_dict[daemon]['no_headers'] = False
                        print(f'[STATE] State {daemon} writing: {",".join(values)}')
                        state.write(f"{','.join(values)}\n")
            time.sleep(state_collector_time)
        if check_all_n_completions(agents_dict.keys()) > 0:
            break
    print(f'[STATE] Finished state collector')


def stats_collector(filename, daemon, agents_dict):
    with open(filename, 'w') as file_:
        file_.write("seconds,cpu,ram,avg_disk_read,avg_disk_write,total_disk_read,total_disk_write\n")
        while check_all_n_completions(agents_dict.keys()) == 0:
            if check_all_n_attempts(agents_dict.keys()) > 0:
                stats = get_stats(daemon)
                if stats:
                    cpu, ram, avg_disk_write, avg_disk_read = stats[:4]
                    print(f'[STATS] Stats {daemon} writing: {time.time()},{cpu},{ram},{avg_disk_read},'
                          f'{avg_disk_write},,')
                    file_.write(f'{time.time()},{cpu},{ram},{avg_disk_read},{avg_disk_write},,\n')
            time.sleep(setup_environment_time)
    finish_stats_collector(agents_dict, daemon, filename)


def finish_stats_collector(agents_dict, daemon, filename):
    if check_all_n_completions(agents_dict.keys()) > 0:
        while True:
            stats = get_stats(daemon)
            if stats:
                print(f'[STATS] Finishing stats {daemon} writing: {time.time()},{",".join(stats)}')
                with open(filename, 'a') as file_:
                    file_.write(f'{time.time()},{",".join(get_stats(daemon))}\n')
                break


@pytest.mark.parametrize('case, modify_file, modify_all, restore_all', [
    (Cases.case0.value, False, False, True),
    (Cases.case1.value, True, False, False),
    (Cases.case2.value, False, True, False)
])
@pytest.mark.parametrize('protocol, eps, files, directory, buffer', [
    ('udp', '200', '0', '/test0k', 'no'),
    ('tcp', '200', '0', '/test0k', 'no'),
    ('udp', '200', '5000', '/test5k', 'no'),
    ('udp', '5000', '5000', '/test5k', 'no'),
    ('tcp', '200', '5000', '/test5k', 'no'),
    ('tcp', '5000', '5000', '/test5k', 'no'),
    ('udp', '200', '50000', '/test50k', 'no'),
    ('udp', '5000', '50000', '/test50k', 'yes'),
    ('tcp', '200', '50000', '/test50k', 'no'),
    ('tcp', '5000', '50000', '/test50k', 'yes'),
    ('udp', '5000', '1000000', '/test1M', 'yes'),
    ('udp', '1000000', '1000000', '/test1M', 'yes'),
    ('tcp', '5000', '1000000', '/test1M', 'yes'),
    ('tcp', '1000000', '1000000', '/test1M', 'yes')
])
def test_initialize_stats_collector(protocol, eps, files, directory, buffer, case, modify_file, modify_all,
                                    restore_all):
    agents_dict = get_agents()
    agents_checker, writers = list(), list()
    database_params = {
        'modify_file': modify_file,
        'modify_all': modify_all,
        'restore_all': restore_all,
        'directory': directory,
        'total_files': files,
        'prefix': 'file_'
    }

    if not (case == 1 and files == '0') and not (case == 2 and files == '0'):
        print('\n\n[SETUP] Setting up the environment...')
        truncate_file(ALERT_FILE_PATH)
        if case == Cases.case0.value:
            replace_conf(protocol, eps, directory, buffer)

        for agent_id in agents_dict.keys():
            filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    f"stats/info_case{case}-{protocol}_{eps}eps_{files}files_{buffer}.csv")
            agents_checker.append(Process(target=agent_checker, args=(case, agent_id, agents_dict, filename,
                                                                      database_params, )))
            agents_checker[-1].start()

        seconds = 0
        while check_all_n_attempts(agents_dict.keys()) != 0 and any(agent != 0.0 for agent in agents_dict.values()):
            print(f'[SETUP] Waiting for agent attempt... {seconds} seconds')
            time.sleep(setup_environment_time)
            seconds += setup_environment_time

        print(f'[ENV] Starting test for case{case}-{protocol}-{eps}eps-{files}files')
        state_collector_check = Process(target=state_collector, args=(case, protocol, eps, files, agents_dict, buffer,))
        state_collector_check.start()
        for daemon in tested_daemons:
            filename = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    f"stats/results_case{case}-{daemon}_{protocol}_{eps}eps_{files}"
                                    f"files_{buffer}.csv")
            writers.append(Process(target=stats_collector, args=(filename, daemon, agents_dict,)))
            writers[-1].start()
        while True:
            if not any([writer_.is_alive() for writer_ in writers]) and \
                    not any([check_agent.is_alive() for check_agent in agents_checker]) and \
                    not state_collector_check.is_alive():
                print('[ENV] All processes are finished')
                break
