from os.path import isdir, join
from shutil import rmtree, ignore_patterns
import os
import json
import stat
from .configuration import PlatformJvmConfiguration, DockerContainerConfiguration
from .properties import Properties, RAISE_ON_EXISTING, INSERT
from .utils import copytree
from .commands import PlatformCommandBuilder


ENVIRONMENT_KEY='ENVIRONMENT'
DATA_CENTER_KEY='DATA_CENTER'
APPLICATION_KEY='APPLICATION'
STRIPE_KEY='STRIPE'
INSTANCE_KEY='INSTANCE'


def _build_properties_from_files(properties, filenames, common_directory):
    if isinstance(filenames, str):
        filenames = [filenames]

    for filename in reversed(filenames):
        properties.merge_with(Properties().build_from_file(join(common_directory, filename)))


class Deployment(object):
    def __init__(self, **kwargs):
        self._properties = Properties()
        self.properties.save(ENVIRONMENT_KEY, kwargs['environment'], behavior=RAISE_ON_EXISTING)
        self.properties.save(DATA_CENTER_KEY, kwargs['data_center'], behavior=RAISE_ON_EXISTING)
        self._common_dir = kwargs.get('common_dir', join('common', self.environment, self.data_center))
        self.properties.save(APPLICATION_KEY, kwargs['application'], behavior=RAISE_ON_EXISTING)
        _build_properties_from_files(self.properties,
                kwargs.get('properties', "%s.properties" % self.application), self.common_directory)
        self.properties.save(STRIPE_KEY, kwargs['stripe'], behavior=RAISE_ON_EXISTING)
        self.properties.save(INSTANCE_KEY, kwargs['instance'], behavior=RAISE_ON_EXISTING)
        self._overrides_dir = kwargs.get('overrides_dir', join('overrides', self.application, self.stripe, self.instance))
        self._builders = kwargs.get('builders', [])

    def __str__(self):
        return str(self._properties)

    @property
    def properties(self):
        return self._properties

    @property
    def environment(self):
        return self.properties[ENVIRONMENT_KEY]

    @property
    def data_center(self):
        return self.properties[DATA_CENTER_KEY]

    @property
    def application(self):
        return self.properties[APPLICATION_KEY]

    @property
    def stripe(self):
        return self.properties[STRIPE_KEY]

    @property
    def instance(self):
        return self.properties[INSTANCE_KEY]

    @property
    def common_directory(self):
        return self._common_dir

    @property
    def overrides_directory(self):
        return self._overrides_dir

    @property
    def output_directory(self):
        return join(os.path.abspath(os.getcwd()), "deployments", self.environment, self.data_center, self.application, self.stripe, self.instance)

    def _get_expanded_configuration(self, configuration):
        for filename in [join(self.common_directory, 'common_params.json'), join(self.overrides_directory, 'app_params.json')]:
            with open(filename, 'r') as json_file:
                configuration = configuration.merge_with(json.load(json_file))
        return configuration.apply_properties(self.properties)

    @property
    def platform_configuration(self):
        if not hasattr(self, '_platform_configuration'):
           self._platform_configuration = self._get_expanded_configuration(PlatformJvmConfiguration({'vmArgs': {'appName': self.stripe}}))
        return self._platform_configuration

    @property
    def docker_container_configuration(self):
        if not hasattr(self, '_docker_configuration'):
            self._docker_configuration = self._get_expanded_configuration(DockerContainerConfiguration())
        return self._docker_configuration

    def load_configurations(self):
        self.platform_configuration
        self.docker_container_configuration

    def create(self):
        self._clean_output_directory()
        self._copy_instance_files()
        self._copy_common_files()
        for builder in self._builders:
            builder.build(self, write_to_file=True)

    def _clean_output_directory(self):
        if isdir(self.output_directory):
            rmtree(self.output_directory)

    def _copy_instance_files(self):
        self._copy_files(self.overrides_directory, ignore=ignore_patterns('app_params.json', '.*'))

    def _copy_common_files(self):
        self._copy_files(self.common_directory, ignore=ignore_patterns('common_params.json', '*.properties', '.*'))

    def _copy_files(self, source, ignore):
        copytree(source, self.output_directory, ignore=ignore, copy_function=self._copy_file)

    def _copy_file(self, source, destination):
        with open(source, 'r') as src, open(destination, 'w') as dst:
            line_no = 1
            for line in src:
                try:
                    dst.write(self.properties.apply_to_value(line))
                    line_no += 1
                except KeyError as e:
                    print("Failed to copy", source, "to", destination)
                    print("Failed while applying properties to line", line_no)
                    print("\t", line)
                    raise e
