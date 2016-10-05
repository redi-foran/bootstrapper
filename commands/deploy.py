import json
import importlib.util
import os.path
import os
import shutil
import contextlib

@contextlib.contextmanager
def work_in_directory(directory):
    current_directory = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(current_directory)


class DeploymentGenerator(object):
    def __init__(self, deployment_loader):
        self._load_deployments = deployment_loader

    def run(self, args):
        if not os.path.isdir(args.path):
            raise Exception("bar")

        if os.path.isdir(os.path.join(args.path, 'deployments')):
            shutil.rmtree(os.path.join(args.path, 'deployments'))

        deployments = self._load_deployments(args.path)
        with work_in_directory(args.path):
            for deployment in deployments:
                deployment.create()


def add_command(deploy_command, deployment_loader):
    generator = DeploymentGenerator(deployment_loader)
    deploy_command.add_argument('--path', '-p', default=os.getcwd())
    deploy_command.set_defaults(callback=generator.run)
