from bootstrapper import RUN_DIRECTORY_KEY
from bootstrapper.location import Location, ENVIRONMENT_TABLE, DATA_CENTER_TABLE
from bootstrapper.commands import CommandBuilder, DockerCommandBuilder, PlatformCommandBuilder
from tempfile import TemporaryDirectory, TemporaryFile
from contextlib import contextmanager
import os, subprocess, shutil, tarfile, http.client, urllib.parse, urllib.request, json, socket

_DOCKER_CONTAINER = 'docker-container'
_PLATFORM_JVM = 'platform-jvm'


def _get_local_ip_address(netinfo_url):
    parts = urllib.parse.urlparse(netinfo_url, 'http')
    port = 80
    if parts.port is None:
        if parts.scheme == 'https':
            port = 443
    else:
        port = parts.port
    s = socket.socket()
    try:
        s.connect((parts.hostname, port))
        return s.getsockname()[0]
    finally:
        s.close()


def _find_deployment(deployments, location, application, stripe, instance):
    for deployment in deployments:
        if deployment.environment == location.environment and \
                deployment.data_center == location.data_center and \
                deployment.application == application and \
                deployment.stripe == stripe and \
                deployment.instance == instance:
                    return deployment
    return None


@contextmanager
def _change_directory(directory):
    current_dir = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(current_dir)


class DeploymentRunner(object):
    def __init__(self):
        self._command_builders = {}
        self._load_deployments = None

    def run(self, args):
        self._args = args
        self._determine_location()
        self._pull_deployment_info()
        with TemporaryDirectory() as self._source_directory_base:
            self._pull_configuration()
            self._generate_run_directory()
            self._pull_package()
            self._populate_run_directory()
        result = self._execute()

    def add_command_builder(self, name, builder):
        if not issubclass(builder, CommandBuilder):
            raise TypeError("builder must be a CommandBuilder")
        elif name in self._command_builders:
            raise KeyError("Builder for '%s' already exists" % name)
        self._command_builders[name] = builder

    @property
    def command_builders(self):
        return self._command_builders.keys()

    def _determine_location(self):
        hostname = getattr(self._args, 'hostname', None)
        if hostname is None:
            environment = getattr(self._args, 'environment', None)
            data_center = getattr(self._args, 'data_center', None)
            if environment is None or data_center is None:
                local_ip_address = _get_local_ip_address(self._args.netinfo_url)
                url = "%s/netinfo/ip/%s" % (self._args.netinfo_url, local_ip_address)
                with urllib.request.urlopen(url) as response:
                    netinfo = json.loads(response.read().decode('utf-8'))['netinfo']
                    if isinstance(netinfo, str):
                        environment = 'dev'
                        data_center = 'AM1'
                        logger.warning("%s. Defaulting to environment=%s, data_center=%s", netinfo, environment, data_center)
                    else:
                        environment = netinfo.get('state', 'dev').lower()
                        if environment == 'uat':
                            environment = 'qa'
                        data_center = "%s%d" % (netinfo.get('region', 'AM'), netinfo.get('region_side', 1))
            self._location = Location(environment=environment, data_center=data_center)
        else:
            self._location = Location(hostname=self._args.hostname)

    @property
    def location(self):
        return self._location

    @property
    def run_directory(self):
        return os.path.join(self.deployment.properties.get(RUN_DIRECTORY_KEY, os.path.join(os.sep, 'var', 'redi', 'runtime')), self._args.application, self._args.stripe, self._args.instance)

    @property
    def _source_directory(self):
        return os.path.join(self._source_directory_base, self._source_directory_specific)

    @property
    def _source_directory_specific(self):
        return os.path.join('deployments', self.deployment.environment, self.deployment.data_center, self.deployment.application, self.deployment.stripe, self.deployment.instance)

    @property
    def deployment_info(self):
        return self._deployment_info

    def _remove_stale_paths(self):
        for path in os.listdir(self.run_directory):
            if path in ['logs', 'data']:
                continue
            full_pathname = os.path.join(self.run_directory, path)
            if os.path.isdir(full_pathname):
                shutil.rmtree(full_pathname)
            else:
                os.remove(full_pathname)

    def _generate_run_directory(self):
        if os.path.isdir(self.run_directory):
            self._remove_stale_paths()
        else:
            os.makedirs(self.run_directory)

    def _populate_run_directory(self):
        for path in os.listdir(self._source_directory):
            source_pathname = os.path.join(self._source_directory, path)
            target_pathname = os.path.join(self.run_directory, path)
            if os.path.isdir(source_pathname):
                shutil.copytree(source_pathname, target_pathname)
            else:
                shutil.copy(source_pathname, target_pathname)

    @property
    def _deployment_url(self):
        return "%s/deployments/%s/%s/%s/%s/%s.json" % (self._args.deployments_url,
                self.location.environment, self.location.data_center, self._args.application, self._args.stripe, self._args.instance)

    def _pull_deployment_info(self):
        with urllib.request.urlopen(self._deployment_url) as response:
            self._deployment_info = json.loads(response.read().decode('utf-8'))

    @property
    def _should_validate(self):
        return self._args.validate

    @property
    def _use_local_configuration(self):
        return self._args.local

    @property
    def _git_repository(self):
        if self._use_local_configuration:
            return os.getcwd()
        return self.deployment_info['git_repository']

    @property
    def _configuration_version(self):
        return self.deployment_info['configuration_version']

    @property
    def _artifact_url(self):
        return self.deployment_info['artifact_download_url']

    def _pull_package(self):
        if self._artifact_url is None:
            raise KeyError("Could not find artifact uri for package=%s, name=%s, version=%s" %
                    (self.deployment_info['artifact_package'], self.deployment_info['artifact_name'], self.deployment_info['artifact_version']))
        with urllib.request.urlopen(self._artifact_url) as response, TemporaryFile(mode='w+b', suffix='tar') as f:
            f.write(response.read())
            f.seek(0)
            with tarfile.open(fileobj=f) as tar, TemporaryDirectory() as directory:
                for tar_member in tar.getmembers():
                    self._extract_member(tar, tar_member, directory)

    def _extract_member(self, tar, tar_member, directory):
        index = tar_member.name.find('/')
        # Safety: Do not extract anything beginning with '/'
        if index > 0:
            target = os.path.join(self.run_directory, tar_member.name[index + 1:])
            if tar_member.isdir() and not os.path.isdir(target):
                os.makedirs(target)
            elif tar_member.isfile() and not os.path.exists(target):
                tar.extract(tar_member, path=directory)
                shutil.move(os.path.join(directory, tar_member.name), target)

    def _pull_configuration(self):
        self._clone_configuration()
        with _change_directory(self._source_directory_base):
            self._switch_configuration_to_version()
            self._obtain_deployment()
            self._build_deployment()
            self._validate_configuration()

    def _clone_configuration(self):
        if self._use_local_configuration:
            for path in os.listdir(os.getcwd()):
                if os.path.isdir(path):
                    shutil.copytree(path, os.path.join(self._source_directory_base, path))
                else:
                    shutil.copy(path, os.path.join(self._source_directory_base, path))
        else:
            subprocess.run(['git', 'clone', self._git_repository, self._source_directory_base], stderr=subprocess.STDOUT)

    def _switch_configuration_to_version(self):
        if not self._use_local_configuration:
            with _change_directory(self._source_directory_base):
                subprocess.run(['git', 'checkout', self._configuration_version], stderr=subprocess.STDOUT)

    def _obtain_deployment(self):
        self.deployment = _find_deployment(self._load_deployments(self._source_directory_base), self.location, self._args.application, self._args.stripe, self._args.instance)
        if self.deployment is None:
            raise KeyError("Failed to find deployment for environment=%s, data center=%s, application=%s, stripe=%s, instance=%s" %
                    (self.location.environment, self.location.data_center, self._args.application, self._args.stripe, self._args.instance))
        self.deployment.load_configurations()

    def _build_deployment(self):
        if os.path.isdir('deployments'):
            shutil.rmtree('deployments')
        self.deployment.create()

    def _validate_configuration(self):
        if not self._use_local_configuration and self._should_validate:
            result = subprocess.run(['git', 'status', '--porcelain', self._source_directory_specific], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if len(result.stdout) > 0:
                raise AssertionError("Configuration validation has failed because the following files are not the same as versioned:\n%s" % result.stdout)

    def _execute(self):
        command_builder = self._command_builders[self._args.mode]()
        command_builder.build(self.deployment, write_to_file=False)
        return command_builder.execute(self)

runner = DeploymentRunner()
runner.add_command_builder(_DOCKER_CONTAINER, DockerCommandBuilder)
runner.add_command_builder(_PLATFORM_JVM, PlatformCommandBuilder)
