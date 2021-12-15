import argparse
import os
import sys
from tempfile import gettempdir

from wazuh_testing.qa_ctl.configuration.config_instance import ConfigInstance
from wazuh_testing.qa_ctl.configuration.config_generator import QACTLConfigGenerator
from wazuh_testing.qa_ctl.provisioning.ansible import playbook_generator
from wazuh_testing.tools.s3_package import get_production_package_url, get_last_production_package_url
from wazuh_testing.tools.time import get_current_timestamp
from wazuh_testing.tools import file
from wazuh_testing.qa_ctl.provisioning import local_actions
from wazuh_testing.tools import github_checks
from wazuh_testing.tools.logging import Logging
from wazuh_testing.tools.exceptions import QAValueError
from wazuh_testing.qa_ctl import QACTL_LOGGER
from wazuh_testing.tools.github_api_requests import WAZUH_QA_REPO

TMP_FILES = os.path.join(gettempdir(), 'wazuh_check_files')
WAZUH_QA_FILES = os.path.join(TMP_FILES, 'wazuh-qa')
CHECK_FILES_TEST_PATH = os.path.join(WAZUH_QA_FILES, 'tests', 'check_files')

logger = Logging(QACTL_LOGGER)
test_build_files = []

def get_parameters():
    """
    Returns:
        argparse.Namespace: Object with the user parameters.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('--action', '-a', type=str, action='store', required=False, dest='test_action',
                        choices=['install', 'upgrade', 'uninstall'], default='install',
                        help='Wazuh action to be carried out to check the check-files')

    parser.add_argument('--os', '-o', type=str, action='store', required=False, dest='os_system',
                        choices=['centos_7', 'centos_8', 'ubuntu'], default='ubuntu')

    parser.add_argument('--version', '-v', type=str, action='store', required=False, dest='wazuh_version',
                        help='Wazuh installation and tests version.')

    parser.add_argument('--debug', '-d', action='count', default=0, help='Run in debug mode. You can increase the debug'
                                                                         ' level with more [-d+]')

    parser.add_argument('--persistent', '-p', action='store_true',
                        help='Persistent instance mode. Do not destroy the instances once the process has finished.')

    parser.add_argument('--qa-branch', type=str, action='store', required=False, dest='qa_branch', default='master',
                        help='Set a custom wazuh-qa branch to download and run the tests files')

    parser.add_argument('--target', '-t', type=str, action='store', required=False, dest='wazuh_target',
                        choices=['manager', 'agent'], default='manager', help='Wazuh test target. manager or agent')

    parser.add_argument('--no-validation', action='store_true', help='Disable the script parameters validation.')

    parser.add_argument('--baseline', action='store_true', help='Launch the test using the check-files baseline data '
                                                                'instead of getting them directly on the initial '
                                                                'status')
    arguments = parser.parse_args()

    return arguments


def set_environment(parameters):
    """Prepare the local environment for the test run.

    Args:
        parameters (argparse.Namespace): Object with the user parameters.

    """
    set_logger(parameters)

    # Download wazuh-qa repository to launch the check-files test files.
    local_actions.download_local_wazuh_qa_repository(branch=parameters.qa_branch, path=TMP_FILES)
    test_build_files.append(WAZUH_QA_FILES)


def set_logger(parameters):
    """Set the test logging.

    Args:
        parameters (argparse.Namespace): Object with the user parameters.
    """
    level = 'DEBUG' if parameters.debug >= 1 else 'INFO'
    logger.set_level(level)

    # Disable traceback if it is not run in DEBUG mode
    if level != 'DEBUG':
        sys.tracebacklimit = 0


def validate_parameters(parameters):
    """Validate input script parameters.

    Raises:
        QAValueError: If a script parameters has a invalid value.
    """
    logger.info('Validating input parameters')

    # Check if QA branch exists
    if not github_checks.branch_exists(parameters.qa_branch, repository=WAZUH_QA_REPO):
        raise QAValueError(f"{parameters.qa_branch} branch does not exist in Wazuh QA repository.",
                           logger.error, QACTL_LOGGER)

    # Check version parameter
    if parameters.wazuh_version and len((parameters.wazuh_version).split('.')) != 3:
        raise QAValueError(f"Version parameter has to be in format x.y.z. You entered {parameters.wazuh_version}",
                           logger.error, QACTL_LOGGER)

    # Check if Wazuh has the specified version
    if parameters.wazuh_version and not github_checks.version_is_released(parameters.wazuh_version):
        raise QAValueError(f"The wazuh {parameters.wazuh_version} version has not been released. Enter a right "
                           'version.', logger.error, QACTL_LOGGER)
    logger.info('Input parameters validation has passed successfully')


def generate_qa_ctl_configuration(parameters, playbooks_path, qa_ctl_config_generator):
    """Generate the qa-ctl configuration according to the script parameters and write it into a file.

    Args:
        parameters (argparse.Namespace): Object with the user parameters.
        playbook_path (list(str)): List with the playbooks path to run with qa-ctl
        qa_ctl_config_generator (QACTLConfigGenerator): qa-ctl config generator object.

    Returns:
        str: Configuration file path where the qa-ctl configuration has been saved.
    """

    logger.info('Generating qa-ctl configuration')

    current_timestamp = str(get_current_timestamp()).replace('.', '_')
    config_file_path = os.path.join(TMP_FILES, f"check_files_config_{current_timestamp}.yaml")
    os_system = parameters.os_system

    instance_name = f"check_files_{os_system}_{current_timestamp}"
    instance = ConfigInstance(instance_name, os_system)

    # Generate deployment configuration
    deployment_configuration = qa_ctl_config_generator.get_deployment_configuration([instance])

    # Generate tasks configuration data
    tasks_configuration = qa_ctl_config_generator.get_tasks_configuration([instance], playbooks_path)

    # Generate qa-ctl configuration file
    qa_ctl_configuration = {**deployment_configuration, **tasks_configuration}
    file.write_yaml_file(config_file_path, qa_ctl_configuration)
    test_build_files.append(config_file_path)

    logger.info(f"The qa-ctl configuration has been created successfully in {config_file_path}")

    return config_file_path


def generate_test_playbooks(parameters, local_checkfiles_pre_data_path, local_checkfiles_post_data_path):
    """Generate the necessary playbooks to run the test.

    Args:
        parameters (argparse.Namespace): Object with the user parameters.
        local_checkfiles_pre_data_path (str): Local path where the pre-check-files data will be saved.
        local_checkfiles_post_data_path (str): Local path where the post-check-files data will be saved.
    """
    playbooks_path = []
    package_url = get_production_package_url(parameters.wazuh_target, parameters.os_system, parameters.wazuh_version) \
        if parameters.wazuh_version else get_last_production_package_url(parameters.wazuh_target, parameters.os_system)
    package_name = os.path.split(package_url)[1]

    check_files_tool_url = f"https://raw.githubusercontent.com/wazuh/wazuh-qa/{parameters.qa_branch}/deps/" \
                           'wazuh_testing/wazuh_testing/scripts/check_files.py'
    os_platform = 'linux'
    package_destination = '/tmp'
    check_files_tool_destination = '/bin/check_files.py'
    ignore_check_files_path = ['/sys', '/proc', '/run', '/dev', '/var/ossec', '/bin/check_files.py']
    check_files_extra_args = '' if parameters.debug == 0 else ('-d' if parameters.debug == 1 else '-dd')
    pre_check_files_data_output_path = '/pre_check_files_data.json'
    post_check_files_data_output_path = '/post_check_files_data.json'
    pre_check_files_command = f"python3 {check_files_tool_destination} -p / -i {' '.join(ignore_check_files_path)} " \
                              f"-o {pre_check_files_data_output_path} {check_files_extra_args}"
    post_check_files_command = f"python3 {check_files_tool_destination} -p / -i {' '.join(ignore_check_files_path)} " \
                               f"-o {post_check_files_data_output_path} {check_files_extra_args}"
    # Playbook parameters
    wazuh_install_playbook_parameters = {'wazuh_target': parameters.wazuh_target, 'package_name': package_name,
                                         'package_url': package_url, 'package_destination': package_destination,
                                         'os_system': parameters.os_system, 'os_platform': os_platform}

    download_files_playbook_parameters = {'files_data': {check_files_tool_url: check_files_tool_destination},
                                          'playbook_parameters': {'become': True}}

    run_pre_check_files_playbook_parameters = {'commands': [pre_check_files_command],
                                               'playbook_parameters': {'become': True}}

    run_post_check_files_playbook_parameters = {'commands': [post_check_files_command],
                                                'playbook_parameters': {'become': True}}

    fetch_files_playbook_parameters = {
        'files_data': {post_check_files_data_output_path: local_checkfiles_post_data_path},
        'playbook_parameters': {'become': True}}

    upgrade_wazuh_playbook_parameters = {'package_name': package_name,  'package_url': package_url,
                                         'package_destination': package_destination, 'os_system': parameters.os_system,
                                         'os_platform': os_platform}

    uninstall_wazuh_playbook_parameters = {'wazuh_target': parameters.wazuh_target, 'os_system': parameters.os_system,
                                           'os_platform': os_platform}

    # Playbooks builder section

    # Add playbook for downloading the check-files tool in the remote host
    playbooks_path.append(playbook_generator.download_files(**download_files_playbook_parameters))

    if not parameters.baseline:
        # Add pre-check-files task
        playbooks_path.append(playbook_generator.run_linux_commands(**run_pre_check_files_playbook_parameters))
        # Add task for fetching pre-check-files data
        fetch_files_playbook_parameters['files_data'].update({
            pre_check_files_data_output_path: local_checkfiles_pre_data_path
        })

    if parameters.test_action == 'install':
        # 1. - Install Wazuh on remote host
        # 2. - Wait 30 seconds before running check-files tool
        playbooks_path.append(playbook_generator.install_wazuh(**wazuh_install_playbook_parameters))
        playbooks_path.append(playbook_generator.wait_seconds(30))

    elif parameters.test_action == 'upgrade':
        wazuh_pre_version = '4.2.0'
        install_package_url = get_production_package_url(parameters.wazuh_target, parameters.os_system,
                                                         wazuh_pre_version)
        install_package_name = os.path.split(install_package_url)[1]
        upgrade_package_url = get_last_production_package_url(parameters.wazuh_target, parameters.os_system)
        upgrade_package_name = os.path.split(upgrade_package_url)[1]
        wazuh_install_playbook_parameters.update({'package_url': install_package_url,
                                                  'package_name': install_package_name})
        upgrade_wazuh_playbook_parameters.update({'package_url': upgrade_package_url,
                                                  'package_name': upgrade_package_name})
        # 1. - Install Wazuh on remote host
        # 2. - Wait 30 seconds before upgrading Wazuh
        # 3. - Upgrade Wazuh on remote host
        # 4. - Wait 30 seconds before running check-files tool
        playbooks_path.append(playbook_generator.install_wazuh(**wazuh_install_playbook_parameters))
        playbooks_path.append(playbook_generator.wait_seconds(30))
        playbooks_path.append(playbook_generator.upgrade_wazuh(**upgrade_wazuh_playbook_parameters))
        playbooks_path.append(playbook_generator.wait_seconds(30))

    elif parameters.test_action == 'uninstall':
        # 1. - Install Wazuh on remote host
        # 2. - Wait 30 seconds before uninstalling Wazuh
        # 3. - Uninstall Wazuh on remote host
        playbooks_path.append(playbook_generator.install_wazuh(**wazuh_install_playbook_parameters))
        playbooks_path.append(playbook_generator.wait_seconds(30))
        playbooks_path.append(playbook_generator.uninstall_wazuh(**uninstall_wazuh_playbook_parameters))

    # Add playbook for running the check-files tool
    playbooks_path.append(playbook_generator.run_linux_commands(**run_post_check_files_playbook_parameters))
    # Add playbook for fetching the check-files data
    playbooks_path.append(playbook_generator.fetch_files(**fetch_files_playbook_parameters))

    return playbooks_path


def main():
    """Run the check-files test according to the script parameters."""
    try:
        parameters = get_parameters()
        qa_ctl_config_generator = QACTLConfigGenerator()
        current_timestamp = str(get_current_timestamp()).replace('.', '_')
        pre_check_files_data_path = os.path.join(TMP_FILES, f"pre_check_files_data_{current_timestamp}.yaml")
        post_check_files_data_path = os.path.join(TMP_FILES, f"post_check_files_data_{current_timestamp}.yaml")

        # Set logging and Download QA files
        set_environment(parameters)

        # Validate script parameters
        if not parameters.no_validation:
            validate_parameters(parameters)

        # Generate the test playbooks to run with qa-ctl
        playbooks_path = generate_test_playbooks(parameters, post_check_files_data_path, pre_check_files_data_path)
        test_build_files.extend(playbooks_path)

        # Generate the qa-ctl configurationgenerate_qa_ctl_configuration
        qa_ctl_config_file_path = generate_qa_ctl_configuration(parameters, playbooks_path, qa_ctl_config_generator)

        # Run the qa-ctl with the generated configuration. Launch deployment + custom playbooks.
        qa_ctl_extra_args = '' if parameters.debug == 0 else ('-d' if parameters.debug == 1 else '-dd')
        qa_ctl_extra_args += ' -p' if parameters.persistent else ''
        local_actions.run_local_command_printing_output(f"qa-ctl -c {qa_ctl_config_file_path} {qa_ctl_extra_args} "
                                                        '--no-validation-logging')
        # Check that the post-check-files data has been fetched correctly
        if os.path.exists(post_check_files_data_path):
            test_build_files.append(post_check_files_data_path)
            logger.info(f"The post-check-files data has been saved in {post_check_files_data_path}")
        else:
            raise QAValueError(f"Could not find the post-check-files data in {TMP_FILES} path", logger.error,
                               QACTL_LOGGER)

        if parameters.baseline:
            pass # Download the S3 file

        # Check that the pre-check-files data has been fetched or downloaded correctly
        if os.path.exists(pre_check_files_data_path):
            test_build_files.append(pre_check_files_data_path)
            logger.info(f"The pre-check-files data has been saved in {pre_check_files_data_path}")
        else:
            raise QAValueError(f"Could not find the pre-check-files data in {TMP_FILES} path", logger.error,
                               QACTL_LOGGER)

        # Launch the check-files pytest
        pytest_launcher = 'python -m pytest' if sys.platform == 'win32' else 'python3 -m pytest'
        pytest_command = f"cd {CHECK_FILES_TEST_PATH} && {pytest_launcher} test_check_files --before-file " \
                         f"{pre_check_files_data_path} --after-file {post_check_files_data_path} " \
                         f"--output-path {TMP_FILES}"
        test_result = local_actions.run_local_command_returning_output(pytest_command)
        print(test_result)
    finally:
        # Clean test build files
        if parameters and not parameters.persistent:
            logger.info('Deleting all test artifacts files of this build (config files, playbooks, data results ...)')
            for file_to_remove in test_build_files:
                file.remove_file(file_to_remove)


if __name__ == '__main__':
    main()
