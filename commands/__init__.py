import json, importlib.util, os.path, os, shutil
from bootstrapper.deployment import Deployment


_DEPLOY_PY = 'deploy.py'
_DEPLOY_JSON = 'deploy.json'


def _load_deployments_from_module(directory):
    return getattr(_load_deployment_module(directory), 'deployments')


def _load_deployments_from_json(directory):
    deployments = []
    with open(os.path.join(directory, _DEPLOY_JSON), 'r') as json_file:
        for d in json.load(json_file):
            deployments.append(Deployment(**d))
    return deployments


def _load_deployments_from_directory(directory):
    deployments = []
    for environment in os.listdir(os.path.join(directory, 'common')):
        for data_center in os.listdir(os.path.join(directory, 'common', environment)):
            properties = []
            for properties_file in os.listdir(os.path.join(directory, 'common', environment, data_center)):
                if properties_file.endswith(".properties"):
                    properties.append(os.path.join(directory, 'common', environment, data_center, properties_file))
            for application in os.listdir(os.path.join(directory, 'overrides')):
                for stripe in os.listdir(os.path.join(directory, 'overrides', application)):
                    for instance in os.listdir(os.path.join(directory, 'overrides', application, stripe)):
                        deployments.append(Deployment(
                            environment=environment,
                            data_center=data_center,
                            application=application,
                            stripe=stripe,
                            instance=instance,
                            properties=properties))
    return deployments


def _load_deployments(directory=os.getcwd()):
    if os.path.exists(os.path.join(directory, _DEPLOY_PY)):
        return _load_deployments_from_module(directory)
    elif os.path.exists(os.path.join(directory, _DEPLOY_JSON)):
        return _load_deployments_from_json(directory)
    elif os.path.isdir(os.path.join(directory, 'common')) and os.path.isdir(os.path.join(directory, 'overrides')):
        return _load_deployments_from_directory(directory)
    else:
        raise RuntimeError("Could not load a deployments the bootstrapper could not find either '%s', '%s', or 'common' and 'overrides' directories." % (_DEPLOY_PY, _DEPLOY_JSON))


def _load_deployment_module(directory=os.getcwd()):
    deploy_py_filename = os.path.join(directory, _DEPLOY_PY)
    spec = importlib.util.spec_from_file_location('deploy', deploy_py_filename)
    if spec is None:
        raise Exception("Found '%s' but failed to load module", deploy_py_filename)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_commands(command_parser):
    from .deploy import add_command as add_deploy_command
    add_deploy_command(command_parser.add_parser('deploy', help='Builds the deployments'), _load_deployments)

    from .run import add_command as add_run_command
    add_run_command(command_parser.add_parser('run', help='Executes a deployment'), _load_deployments)

    from .stop import add_command as add_stop_command
    add_stop_command(command_parser.add_parser('stop', help='Stops a running process'), _load_deployments)
