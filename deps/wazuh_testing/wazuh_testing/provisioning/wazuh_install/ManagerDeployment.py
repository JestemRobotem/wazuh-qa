
from wazuh_testing.provisioning.wazuh_install.WazuhDeployment import WazuhDeployment
from wazuh_testing.provisioning.ansible.AnsibleTask import AnsibleTask
from wazuh_testing.provisioning.ansible.AnsibleRunner import AnsibleRunner


class ManagerDeployment(WazuhDeployment):
    """Deploy Wazuh manager with all the elements needed, set from the configuration file

    Args:
        installation_files (string): Path where is located the Wazuh instalation files.
        configuration (WazuhConfiguration): Configuration object to be set.
        inventory_file_path (string): Path where is located the ansible inventory file.
        install_mode (string): 'package' or 'sources' installation mode.
        install_dir_path (string): Path where the Wazuh installation will be stored.
        hosts (string): Group of hosts to be deployed.
        ip_server (string): Manager IP to connect.

    Attributes:
        installation_files (string): Path where is located the Wazuh instalation files.
        configuration (WazuhConfiguration): Configuration object to be set.
        inventory_file_path (string): Path where is located the ansible inventory file.
        install_mode (string): 'package' or 'sources' installation mode.
        install_dir_path (string): Path where the Wazuh installation will be stored.
        hosts (string): Group of hosts to be deployed.
        ip_server (string): Manager IP to connect.
    """

    def install(self):
        """Child method to install Wazuh in manager

        Returns:
            AnsibleOutput: Result of the ansible playbook run.
        """
        super().install('server')

    def start_service(self):
        """Child method to start service in manager

        Returns:
            AnsibleOutput: Result of the ansible playbook run.
        """
        super().start_service('manager')

    def restart_service(self):
        """Child method to start service in manager

        Returns:
            AnsibleOutput: Result of the ansible playbook run.
        """
        super().restart_service('manager')

    def stop_service(self):
        """Child method to start service in manager

        Returns:
            AnsibleOutput: Result of the ansible playbook run.
        """
        super().stop_service('manager')

    def health_check(self):
        """Check if the installation is full complete, and the necessary items are ready

        Returns:
            AnsibleOutput: Result of the ansible playbook run.
        """
        tasks_list = []
        tasks_list.append(AnsibleTask({'name': 'Extract service status',
                                       'command': f'{self.install_dir_path}/bin/wazuh-control status',
                                       'when': 'ansible_system != "Windows"',
                                       'register': 'status',
                                       'failed_when': ['"wazuh-analysisd is running" not in status.stdout or' +
                                                       '"wazuh-db is running" not in status.stdout or' +
                                                       '"wazuh-authd is running" not in status.stdout']}))

        playbook_parameters = {'tasks_list': tasks_list, 'hosts': self.hosts, 'gather_facts': True, 'become': True}

        output = AnsibleRunner.run_ephemeral_tasks(self.inventory_file_path, playbook_parameters)

        if output.rc != 0:
            with open(f'{output.stderr_file}', 'r') as file:
                raise Exception(f"Failed: {file.read()}")
