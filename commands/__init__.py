import json
import importlib.util
import os.path
import os
import shutil
from bootstrapper import Deployment


_DEPLOY_PY = 'deploy.py'
_DEPLOY_JSON = 'deploy.json'


def _load_deployments_from_json(directory):
    deployments = []
    with open(os.path.join(directory, _DEPLOY_JSON), 'r') as json_file:
        for d in json.load(json_file):
            deployments.append(Deployment(**d))
    return deployments


def _load_deployments_from_module(directory):
    return getattr(_load_deployment_module(directory), 'deployments')


def _load_deployments(directory=os.getcwd()):
    if os.path.exists(os.path.join(directory, _DEPLOY_PY)):
        return _load_deployments_from_module(directory)
    elif os.path.exists(os.path.join(directory, _DEPLOY_JSON)):
        return _load_deployments_from_json(directory)
    else:
        raise Exception("foo")


def _load_deployment_module(directory=os.getcwd()):
    spec = importlib.util.spec_from_file_location('deploy', os.path.join(directory, _DEPLOY_PY))
    if spec is None:
        raise Exception("blah")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _add_commands(command_parser):
    from .deploy import _add_command as add_deploy_command
    add_deploy_command(command_parser.add_parser('deploy', help='Builds the deployments'))

    from .run import _add_command as add_run_command
    add_run_command(command_parser.add_parser('run', help='Executes a deployment'))
