import socket
from .runner import DeploymentRunner, START_CALLBACKS
from bootstrapper import ENVIRONMENT_TABLE, DATA_CENTER_TABLE

__all__ = ['_add_command', START_CALLBACKS]

def add_command(run_command, deployment_loader):
    deployment_runner = DeploymentRunner(deployment_loader)
    location_group = run_command.add_mutually_exclusive_group()
    location_group.add_argument('--hostname', default=socket.getfqdn())
    dce_group = location_group.add_argument_group()
    dce_group.add_argument('--data_center', '-l', choices=set(DATA_CENTER_TABLE.values()))
    dce_group.add_argument('--environment', '-e', choices=set(ENVIRONMENT_TABLE.values()))
    run_command.add_argument('--application', '-a', required=True)
    run_command.add_argument('--stripe', '-s', required=True)
    run_command.add_argument('--instance', '-i', required=True)
    run_command.add_argument('--mode', '-m', choices=set(START_CALLBACKS.keys()), default='docker-container')
    run_command.add_argument('--local', action='store_true')
    run_command.add_argument('--validate', action='store_false')
    run_command.set_defaults(callback=deployment_runner.run)
