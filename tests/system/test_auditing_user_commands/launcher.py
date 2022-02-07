import argparse
import os
import sys
from tempfile import gettempdir

from deps.wazuh_testing.wazuh_testing.qa_ctl import QACTL_LOGGER
from deps.wazuh_testing.wazuh_testing.qa_ctl.configuration.config_generator import QACTLConfigGenerator
from deps.wazuh_testing.wazuh_testing.qa_ctl.provisioning import local_actions
from deps.wazuh_testing.wazuh_testing.tools import file, github_checks
from deps.wazuh_testing.wazuh_testing.tools.exceptions import QAValueError
from deps.wazuh_testing.wazuh_testing.tools.github_api_requests import WAZUH_QA_REPO
from deps.wazuh_testing.wazuh_testing.tools.logging import Logging
from deps.wazuh_testing.wazuh_testing.tools.time import get_current_timestamp
from wazuh_testing.tools.s3_package import get_production_package_url, get_last_production_package_url
from wazuh_testing.qa_ctl.provisioning.ansible import playbook_generator

TMP_FILES = os.path.join(gettempdir(), 'wazuh_auditing_commands')
WAZUH_QA_FILES = os.path.join(TMP_FILES, 'wazuh-qa')
CHECK_FILES_TEST_PATH = os.path.join(WAZUH_QA_FILES, 'tests', 'system', 'test_auditing_user_commands')

logger = Logging(QACTL_LOGGER)
test_build_files = []


def get_parameters():
    """
    Returns:
        argparse.Namespace: Object with the user parameters.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('--os', '-o', type=str, action='store', required=False, dest='os_system',
                        choices=['centos_7', 'centos_8'], default='centos_8')

    parser.add_argument('--version', '-v', type=str, action='store', required=False, dest='wazuh_version',
                        help='Wazuh installation and tests version.')

    parser.add_argument('--debug', '-d', action='count', default=0, help='Run in debug mode. You can increase the debug'
                                                                         ' level with more [-d+]')

    parser.add_argument('--persistent', '-p', action='store_true',
                        help='Persistent instance mode. Do not destroy the instances once the process has finished.')

    parser.add_argument('--qa-branch', type=str, action='store', required=False, dest='qa_branch', default='master',
                        help='Set a custom wazuh-qa branch to download and run the tests files')

    parser.add_argument('--deployment-info', type=str, action='store', required=False, dest='deployment_info',
                        help='Path to the file that contains the deployment information. If specified, local instances '
                             'will not be deployed')

    parser.add_argument('--output-file-path', type=str, action='store', required=False, dest='output_file_path',
                        help='Path to store all test results')

    arguments = parser.parse_args()

    return arguments


def set_environment(parameters):
    """Prepare the local environment for the test run.

    Args:
        parameters (argparse.Namespace): Object with the user parameters.

    """
    set_logger(parameters)

    local_actions.download_local_wazuh_qa_repository(branch=parameters.qa_branch, path=TMP_FILES)
    test_build_files.append(WAZUH_QA_FILES)

    if parameters.output_file_path:
        file.recursive_directory_creation(parameters.output_file_path)


def set_logger(parameters):
    """Set the test logging.

    Args:
        parameters (argparse.Namespace): Object with the user parameters.
    """
    level = 'DEBUG' if parameters.debug >= 1 else 'INFO'
    logger.set_level(level)

    if level != 'DEBUG':
        sys.tracebacklimit = 0


def validate_parameters(parameters):
    """Validate input script parameters.

    Raises:
        QAValueError: If a script parameters has a invalid value.
    """
    def validate_deployment_info_data(data):
        """Check that all deployment data required parameters has been specified"""
        required_data = ['ansible_connection', 'ansible_user', 'ansible_port', 'ansible_python_interpreter', 'host',
                         'system']
        for key_data in required_data:
            if key_data not in data.keys():
                return False

        if 'ansible_password' not in data.keys() and 'ansible_ssh_private_key_file' not in data.keys():
            return False

        return True

    logger.info('Validating input parameters')

    if not github_checks.branch_exists(parameters.qa_branch, repository=WAZUH_QA_REPO):
        raise QAValueError(f"{parameters.qa_branch} branch does not exist in Wazuh QA repository.",
                           logger.error, QACTL_LOGGER)

    if parameters.wazuh_version and len((parameters.wazuh_version).split('.')) != 3:
        raise QAValueError(f"Version parameter has to be in format x.y.z. You entered {parameters.wazuh_version}",
                           logger.error, QACTL_LOGGER)

    if parameters.wazuh_version and not github_checks.version_is_released(parameters.wazuh_version):
        raise QAValueError(f"The wazuh {parameters.wazuh_version} version has not been released. Enter a right "
                           'version.', logger.error, QACTL_LOGGER)

    if parameters.deployment_info:
        if not os.path.isfile(parameters.deployment_info) or not os.path.exists(parameters.deployment_info):
            raise QAValueError('The specified deployment-info file does not exist.', logger.error, QACTL_LOGGER)

        if not file.validate_yaml_file(parameters.deployment_info):
            raise QAValueError(f"The deployment-info {parameters.deployment_info} is not in YAML format, or it has "
                               'wrong syntax', logger.error, QACTL_LOGGER)
        deployment_data = file.read_yaml(parameters.deployment_info)

        for item in deployment_data:
            if not validate_deployment_info_data(item):
                raise QAValueError('Some necessary field is missing in the deployment-info file. The necessary one '
                                   'are as follows: [ansible_connection, ansible_user, ansible_port, '
                                   'ansible_python_interpreter, host, system] and (ansible_password | '
                                   'ansible_ssh_private_key_file)')

    logger.info('Input parameters validation has passed successfully')


def generate_test_playbooks(parameters):
    """Generate the necessary playbooks to run the test.
    Args:
        parameters (argparse.Namespace): Object with the user parameters.
    """
    playbooks_info = {}
    manager_package_url = get_production_package_url('manager', parameters.os_system, parameters.wazuh_version) \
        if parameters.wazuh_version else get_last_production_package_url('manager', parameters.os_system)
    manager_package_name = os.path.split(manager_package_url)[1]
    agent_package_url = get_production_package_url('agent', parameters.os_system, parameters.wazuh_version) \
        if parameters.wazuh_version else get_last_production_package_url(parameters.wazuh_target, parameters.os_system)
    agent_package_name = os.path.split(agent_package_url)[1]

    os_platform = 'linux'
    package_destination = '/tmp'
    check_auditd_status = {
    'command': 'systemctl status auditd.service',
    'expected': 'active (running)'
    }
    user_command = {
        'command': 'ping www.google.com',
        'expected': '/user/bin/ping'
    }
    check_agent_audit_config = {
        'command': 'grep -Pzoc "(?s) +<localfile>\n +<log_format>audit.+?(?=localfile)localfile>\n" /var/ossec/etc/ossec.conf',
        'expected': '1'
    }
    store_rule_1 = 'RULE_1_WAZUH="-a exit,always -F euid=$EUID -F arch=b32 -S execve -k audit-wazuh-c"'
    store_rule_2 = 'RULE_2_WAZUH="-a exit,always -F euid=$EUID -F arch=b64 -S execve -k audit-wazuh-c"'
    merge_rules = 'RULES_WAZUH="${RULE_1_WAZUH}\n${RULE_2_WAZUH}"'
    create_rules = 'echo -e "${RULES_WAZUH}" >> /etc/audit/rules.d/wazuh.rules'
    delete_old_rules = 'auditctl -D'
    load_rules_from_file = 'auditctl -R /etc/audit/rules.d/wazuh.rules'

    manager_install_playbook_parameters = {
        'wazuh_target': 'manager', 'package_name': manager_package_name,
        'package_url': manager_package_url, 'package_destination': package_destination,
        'os_system': parameters.os_system, 'os_platform': os_platform
    }

    agent_install_playbook_parameters = {
        'wazuh_target': 'agent', 'package_name': agent_package_name,
        'package_url': agent_package_url, 'package_destination': package_destination,
        'os_system': parameters.os_system, 'os_platform': os_platform
    }


    return playbooks_info


def main():
    """Run the check-files test according to the script parameters."""
    parameters = get_parameters()
    validate_parameters(parameters)
    qa_ctl_config_generator = QACTLConfigGenerator()
    current_timestamp = str(get_current_timestamp()).replace('.', '_')
    test_output_path = parameters.output_file_path if parameters.output_file_path else \
        os.path.join(TMP_FILES, f"test_auditing_commands_result_{current_timestamp}")

    set_environment(parameters)

    try:
        playbooks_info = generate_test_playbooks(parameters)
        test_build_files.extend([playbook_path for playbook_path in playbooks_info.values()])
    finally:
        if parameters and not parameters.persistent:
            logger.info('Deleting all test artifacts files of this build (config files, playbooks, data results ...)')
            for file_to_remove in test_build_files:
                file.remove_file(file_to_remove)


if __name__ == '__main__':
    main()