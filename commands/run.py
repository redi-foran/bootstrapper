from bootstrapper import Location, ENVIRONMENT_TABLE, DATA_CENTER_TABLE
import socket
from . import _load_deployments

_DOCKER_CONTAINER = 'docker-container'
_SHELL_SCRIPT = 'shell-script'


def _find_deployment(deployments, location, application, stripe, instance):
    print("location=", str(location))
    for deployment in deployments:
        if deployment.environment == location.environment and \
                deployment.data_center == location.data_center and \
                deployment.application == application and \
                deployment.stripe == stripe and \
                deployment.instance == instance:
                    return deployment
    return None

def _get_location(args):
    if hasattr(args, 'hostname'):
        return Location(hostname=args.hostname)
    else:
        return Location(environment=args.environment, data_center=args.data_center)


def _run_docker_container(deployment):
    print(str(deployment))


def _run_shell_script(deployment):
    print(str(deployment))


_RUN_CALLBACKS = {
        _DOCKER_CONTAINER: _run_docker_container,
        _SHELL_SCRIPT: _run_shell_script }


def _run_deployment(args):
    deployment = _find_deployment(_load_deployments(), _get_location(args), args.application, args.stripe, args.instance)
    if deployment is not None:
        _RUN_CALLBACKS[args.mode](deployment)


def _add_command(run_command):
    location_group = run_command.add_mutually_exclusive_group()
    location_group.add_argument('--hostname', default=socket.getfqdn())
    dce_group = location_group.add_argument_group()
    dce_group.add_argument('--data_center', '-l', choices=DATA_CENTER_TABLE.values())
    dce_group.add_argument('--environment', '-e', choices=ENVIRONMENT_TABLE.values())
    run_command.add_argument('--application', '-a', required=True)
    run_command.add_argument('--stripe', '-s', required=True)
    run_command.add_argument('--instance', '-i', required=True)
    run_command.add_argument('--mode', '-m', choices=_RUN_CALLBACKS.keys(), default='docker-container')
    run_command.set_defaults(callback=_run_deployment)
