import json
import importlib.util
import os.path
import os
import shutil
from . import _load_deployments


def _deploy(args):
    if not os.path.isdir(args.path):
        raise Exception("bar")

    if os.path.isdir(os.path.join(args.path, 'deployments')):
        shutil.rmtree(os.path.join(args.path, 'deployments'))

    deployments = _load_deployments(args.path)
    os.chdir(args.path)
    for deployment in deployments:
        deployment.create()


def _add_command(deploy_command):
    deploy_command.add_argument('--path', '-p', default=os.getcwd())
    deploy_command.set_defaults(callback=_deploy)
