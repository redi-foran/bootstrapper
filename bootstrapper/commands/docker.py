from .builder import CommandBuilder


class DockerConfiguration(object):
    def __init__(self, configuration):
        self._configuration = configuration

    @property
    def volumes(self):
        return self._configuration.get('dockerContainer', {}).get('volumes', [])

    @property
    def ports(self):
        return self._configuration.get('dockerContainer', {}).get('ports', [])

    @property
    def min_memory(self):
        return self._configuration.get('memory', {}).get('min')

    @property
    def max_memory(self):
        return self._configuration.get('memory', {}).get('max')


class DockerCommandBuilder(CommandBuilder):
    @property
    def executable(self):
        return "docker run"

    def do_build(self, deployment):
        configuration = DockerConfiguration(deployment.configuration)
        self._build_docker_base_arguments()
        self._build_names(deployment.environment, deployment.data_center, deployment.stripe, deployment.application, deployment.instance)
        self._build_ports(configuration.ports)
        self._build_volumes(configuration.volumes)

    def _build_docker_base_arguments(self):
        self.add_argument("--detach")

    def _build_names(self, environment, data_center, application, stripe, instance):
        self.add_argument("--hostname %s-%s-%s-%s-%s.rdti.com", environment, data_center, application, stripe, instance)
        self.add_argument("--name %s-%s-%s", application, stripe, instance)

    def _build_ports(self, ports):
        for port in ports:
            if isinstance(port, dict):
                self.add_argument("--publish %d:%d", int(port['host']), int(port['container']))
            else:
                self.add_argument("--publish %d", int(port))

    def _build_volumes(self, volumes):
        for volume in volumes:
            self.add_argument("--volume %s:%s", volume['host'], volume['container'])

    def execute(self, runner):
        image = "%s:%s" % (runner.version_info['image_name'], runner.version_info['image_version'])
        self._pull_docker_image(image)
        run_directory = runner.run_directory
        if runner.run_directory.startswith(os.getcwd()):
            run_directory = run_directory[len(os.getcwd()):]
        with run_in_directory(runner.run_directory):
            return self._do_execute(self.command + ['--workdir', run_directory, image, os.path.join('scripts', self.start_script_filename)])

    def _pull_docker_image(self, image):
        return subprocess.run(['docker', 'pull', image], stderr=subprocess.STDOUT)
