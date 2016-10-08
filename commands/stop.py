import subprocess


class Stopper(object):
    def __init__(self, deployment_loader):
        self._load_deployments = deployment_loader

    def stop(self, args):
        self._args = args
        if args.mode == 'docker-container':
            self._stop_docker_container()

    def _stop_docker_container(self):
        name = "%s-%s-%s" % (self._args.application, self._args.stripe, self._args.instance)
        docker_ps = subprocess.run(['docker', 'ps', '--all', '--filter', 'name=%s' % name, '--quiet'], stderr=subprocess.DEVNULL, stdout=subprocess.PIPE, universal_newlines=True)
        if docker_ps.stdout is not None:
            subprocess.run(['docker', 'stop', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, universal_newlines=True)
        subprocess.run(['docker', 'rm', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, universal_newlines=True)


def add_command(stop_command, deployment_loader):
    stopper = Stopper(deployment_loader)
    stop_command.add_argument('--application', '-a')
    stop_command.add_argument('--stripe', '-s')
    stop_command.add_argument('--instance', '-i')
    stop_command.add_argument('--mode', '-m', choices=('docker-container',), default='docker-container')
    stop_command.set_defaults(callback=stopper.stop)
