"""Defines the interface for executing a job"""
from __future__ import unicode_literals

import logging
import os

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from job.configuration.interface import job_interface_1_1 as previous_interface
from job.configuration.interface.exceptions import InvalidInterfaceDefinition
from job.execution.container import SCALE_JOB_EXE_INPUT_PATH


logger = logging.getLogger(__name__)

SCHEMA_VERSION = '1.2'

JOB_INTERFACE_SCHEMA = {
    'type': 'object',
    'required': ['command', 'command_arguments'],
    'additionalProperties': False,
    'properties': {
        'version': {
            'description': 'version of the job_interface schema',
            "default": SCHEMA_VERSION,
            "type": "string"
        },
        'command': {
            'description': 'The command that will be called.  Uses variable replacement',
            'type': 'string',
        },
        'command_arguments': {
            'description': 'The arguments that are passed to the command',
            'type': 'string',
        },
        'env_vars': {
            'description': 'Environment variables that will be made available at runtime',
            'type': 'array',
            'items': {
                '$ref': '#/definitions/env_var',
            },
        },
        'settings': {
            'description': 'Job settings that will be in command call',
            'type': 'array',
            'items': {
                '$ref': '#/definitions/setting',
            },
        },
        'input_data': {
            'type': 'array',
            'items': {
                '$ref': '#/definitions/input_data_item',
            },
        },
        'output_data': {
            'type': 'array',
            'items': {
                '$ref': '#/definitions/output_data_item',
            },
        },
        'shared_resources': {
            'type': 'array',
            'items': {
                '$ref': '#/definitions/shared_resource',
            },
        },
    },
    'definitions': {
        'env_var': {
            'type': 'object',
            'required': ['name', 'value'],
            'additionalProperties': False,
            'properties': {
                'name': {
                    'type': 'string',
                },
                'value': {
                    'type': 'string',
                },
            },
        },
        'setting': {
            'type': 'object',
            'required': ['name'],
            'additionalProperties': False,
            'properties': {
                'name': {
                    'type': 'string',
                },
                'required': {
                    'type': 'boolean',
                },
            },
        },
        'input_data_item': {
            'type': 'object',
            'required': ['name', 'type'],
            'additionalProperties': False,
            'properties': {
                'name': {
                    'type': 'string',
                    'pattern': '^[a-zA-Z0-9\\-_ ]{1,255}$',
                },
                'type': {
                    'type': 'string',
                    'enum': ['file', 'files', 'property'],
                },
                'required': {
                    'type': 'boolean',
                },
                'partial': {
                    'description': 'file/files type only flag indicating input may be mounted vs downloaded',
                    'type': 'boolean'
                },
                'media_types': {
                    'type': 'array',
                },
            },
        },
        'output_data_item': {
            'type': 'object',
            'required': ['name', 'type'],
            'additionalProperties': False,
            'properties': {
                'name': {
                    'type': 'string',
                    'pattern': '^[a-zA-Z0-9\\-_ ]{1,255}$',
                },
                'type': {
                    'type': 'string',
                    'enum': ['file', 'files'],
                },
                'required': {
                    'type': 'boolean',
                },
                'media_type': {
                    'type': 'string',
                },
            },
        },
        'shared_resource': {
            'type': 'object',
            'required': ['name', 'type'],
            'additionalProperties': False,
            'properties': {
                'name': {
                    'type': 'string',
                },
                'type': {
                    'type': 'string',
                },
                'required': {
                    'type': 'boolean',
                },
            },
        },
    },
}


class JobInterface(previous_interface.JobInterface):
    """Represents the interface for executing a job"""

    def __init__(self, definition):
        """Creates a job interface from the given definition. If the definition is invalid, a
        :class:`job.configuration.interface.exceptions.InvalidInterfaceDefinition` exception will be thrown.

        :param definition: The interface definition
        :type definition: dict
        """
        self.definition = definition
        self._param_names = set()

        # Tuples used for validation with other classes
        self._property_validation_dict = {}  # str->bool
        self._input_file_validation_dict = {}  # str->tuple
        self._output_file_validation_list = []

        self._output_file_manifest_dict = {}  # str->bool

        if 'version' not in self.definition:
            self.definition['version'] = SCHEMA_VERSION

        if self.definition['version'] != SCHEMA_VERSION:
            self.convert_interface(definition)

        try:
            validate(definition, JOB_INTERFACE_SCHEMA)
        except ValidationError as validation_error:
            raise InvalidInterfaceDefinition(validation_error)

        self._populate_default_values()
        self._populate_settings_defaults()

        self._check_param_name_uniqueness()
        self._validate_command_arguments()
        self._create_validation_dicts()

    @staticmethod
    def convert_interface(interface):
        """Convert the previous Job interface schema to the 1.2 schema

        :param interface: The previous interface
        :type interface: dict
        :return: converted interface
        :rtype: dict
        """
        previous = previous_interface.JobInterface(interface)

        converted = previous.get_dict()

        converted['version'] = SCHEMA_VERSION

        if 'env_vars' not in converted:
            converted['env_vars'] = []

        if 'settings' not in converted:
            converted['settings'] = []

        return converted

    def _populate_settings_defaults(self):
        """populates the default values for any missing settings values"""
        for setting in self.definition['settings']:
            if 'required' not in setting:
                setting['required'] = False

    def _populate_env_vars_defaults(self):
        """populates the default values for any missing environment variable values"""
        for env_var in self.definition['env_vars']:
            if 'value' not in env_var:
                env_var['value'] = ""
