import socket
from .runner import DeploymentRunner, COMMAND_BUILDERS
from bootstrapper import ENVIRONMENT_TABLE, DATA_CENTER_TABLE

__all__ = ['_add_command', COMMAND_BUILDERS]

def add_command(run_command, deployment_loader):
    deployment_runner = DeploymentRunner(deployment_loader)
    location_group = run_command.add_mutually_exclusive_group()
    location_group.add_argument('--hostname', help='Used to determine environment and data center (preferred method if provided)')
    dce_group = location_group.add_argument_group()
    dce_group.add_argument('--data_center', '-l', choices=set(DATA_CENTER_TABLE.values()), help='Used to specify data center (when used with environment)')
    dce_group.add_argument('--environment', '-e', choices=set(ENVIRONMENT_TABLE.values()), help='Used to specify environment (when used with data center)')
    run_command.add_argument('--application', '-a', required=True)
    run_command.add_argument('--stripe', '-s', required=True)
    run_command.add_argument('--instance', '-i', required=True)
    run_command.add_argument('--mode', '-m', choices=set(COMMAND_BUILDERS.keys()), default='docker-container')
    run_command.add_argument('--local', action='store_true', help='Use local directory for configuration for local development testing (skips validation)')
    run_command.add_argument('--skip-validation', action='store_false', help='Skips configuration validation')
    run_command.add_argument('--netinfo-url', default='http://netinfo.rdti.com', help='Used to determine environment and data center when not provided')
    run_command.add_argument('--versions-url', default='http://nydevl0008.rdti.com:8081', help='Used to determine version info for docker image (if run in a container), application binary, and configuration')
    run_command.set_defaults(callback=deployment_runner.run)
