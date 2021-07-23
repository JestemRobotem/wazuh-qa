# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
from abc import ABC, abstractmethod


class Instance(ABC):
    """Abstract class to hold common methods for instance handling"""
    @abstractmethod
    def run(self):
        """Method to start the instance."""
        pass

    @abstractmethod
    def restart(self):
        """Method to restart the instance."""
        pass

    @abstractmethod
    def halt(self):
        """Method to stop the instance."""
        pass

    @abstractmethod
    def destroy(self):
        """Method to destroy the instance."""
        pass

    @abstractmethod
    def get_instance_info(self):
        """Method to get the instance information."""
        pass

    @abstractmethod
    def get_name(self):
        """Method to get the instance name."""
        pass

    @abstractmethod
    def status(self):
        """Method to get the instance status."""
