from bootstrapper import Location, ENVIRONMENT_TABLE, DATA_CENTER_TABLE, DockerCommandBuilder, PlatformCommandBuilder
import os
import subprocess
import shutil
from tempfile import TemporaryDirectory, TemporaryFile
from contextlib import contextmanager
import tarfile
import http.client
import urllib.parse
import urllib.request

_DOCKER_CONTAINER = 'docker-container'
_PLATFORM_JVM = 'platform-jvm'


def _find_deployment(deployments, location, application, stripe, instance):
    for deployment in deployments:
        if deployment.environment == location.environment and \
                deployment.data_center == location.data_center and \
                deployment.application == application and \
                deployment.stripe == stripe and \
                deployment.instance == instance:
                    return deployment
    return None

def _get_location(args):
    if hasattr(args, 'environment') and hasattr(args, 'data_center'):
        return Location(environment=args.environment, data_center=args.data_center)
    elif hasattr(args, 'hostname'):
        return Location(hostname=args.hostname)


def _run_docker_container(deployment, version_info):
    print("Running", os.path.join(deployment.run_directory, 'start_docker_container.sh'))


def _platform_jvm(deployment, version_info):
    print("Running", os.path.join(deployment.run_directory, 'start_platform_jvm.sh'))


@contextmanager
def _change_directory(directory):
    current_dir = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(current_dir)


START_CALLBACKS = {
        _DOCKER_CONTAINER: DockerCommandBuilder,
        _PLATFORM_JVM: PlatformCommandBuilder }


class DeploymentRunner(object):
    def __init__(self, deployment_loader):
        self._load_deployments = deployment_loader

    def run(self, args):
        self._args = args
        self._pull_version_info()
        with TemporaryDirectory() as self._source_directory_base:
            self._pull_configuration()
            self._generate_run_directory()
            self._pull_package()
            self._populate_run_directory()
        result = self._execute()

    @property
    def _run_directory(self):
        return self.deployment.run_directory

    @property
    def _source_directory(self):
        return os.path.join(self._source_directory_base, self._source_directory_specific)

    @property
    def _source_directory_specific(self):
        return os.path.join('deployments', self.deployment.environment, self.deployment.data_center, self.deployment.application, self.deployment.stripe, self.deployment.instance)

    @property
    def version_info(self):
        return self._version_info

    def _remove_stale_paths(self):
        for path in os.listdir(self._run_directory):
            if path in ['logs', 'data']:
                continue
            full_pathname = os.path.join(self._run_directory, path)
            if os.path.isdir(full_pathname):
                shutil.rmtree(full_pathname)
            else:
                os.remove(full_pathname)

    def _generate_run_directory(self):
        if os.path.isdir(self._run_directory):
            self._remove_stale_paths()
        else:
            os.makedirs(self._run_directory)

    def _populate_run_directory(self):
        for path in os.listdir(self._source_directory):
            source_pathname = os.path.join(self._source_directory, path)
            target_pathname = os.path.join(self._run_directory, path)
            if os.path.isdir(source_pathname):
                shutil.copytree(source_pathname, target_pathname)
            else:
                shutil.copy(source_pathname, target_pathname)

    def _pull_version_info(self):
        with urllib.request.urlopen(self._version_url) as response:
            

        self._version_info = {
                'image_name': 'rediforan/img-redi-centos',
                'image_version': 'latest',
                'artifact_package': 'com.redi.oms',
                'artifact_name': 'historic-data',
                'artifact_version': '0.1.0',
                'git_repository': 'git@github.com:redi-foran/config-historic-stream.git',
                'configuration_version': 'latest'}

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
        return self.version_info['git_repository']

    @property
    def _configuration_version(self):
        return self.version_info['configuration_version']

    @property
    def _artifact_url(self):
        return "http://artifactory.rdti.com:80/artifactory/libs-snapshot-local/com/redi/oms/legacyPublishing/LATEST-SNAPSHOT/legacyPublishing-LATEST-SNAPSHOT-release.tar"

    def _pull_package(self):
        with urllib.request.urlopen(self._artifact_url) as response, TemporaryFile(mode='w+b', suffix='tar') as f:
            f.write(response.read())
            f.seek(0)
            with tarfile.open(fileobj=f) as tar, TemporaryDirectory() as directory:
                for tar_member in tar.getmembers():
                    self._extract_member(tar, tar_member, directory)

    def _extract_member(self, tar, tar_member, directory):
        index = tar_member.name.find('/')
        # Safety: Do not extract anything beginning '/'
        if index > 0:
            target = os.path.join(self._run_directory, tar_member.name[index + 1:])
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
            if not self._use_local_configuration and self._should_validate:
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
        location = _get_location(self._args)
        self.deployment = _find_deployment(self._load_deployments(self._source_directory_base), location, self._args.application, self._args.stripe, self._args.instance)
        if self.deployment is None:
            raise KeyError("Failed to find deployment for environment=%s, data center=%s, application=%s, stripe=%s, instance=%s" %
                    (location.environment, location.data_center, self._args.application, self._args.stripe, self._args.instance))
        self.deployment.load_configurations()

    def _validate_configuration(self):
        shutil.rmtree(os.path.join(self._source_directory_base, 'deployments'))
        self.deployment.create()
        result = subprocess.run(['git', 'status', '--porcelain', self._source_directory_specific], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if len(result.stdout) > 0:
            raise AssertionError("Configuration validation has failed because the following files are not the same as versioned:\n%s" % result.stdout)

    def _execute(self):
        command_builder = START_CALLBACKS[self._args.mode]()
        command_builder.build(self.deployment, write_to_file=False)
        return command_builder.execute(self)
