from . import logger
from .configuration import Configuration
from .properties import Properties, RAISE_ON_EXISTING
from .utils import copytree
import os, os.path, json, shutil, stat


ENVIRONMENT_KEY='ENVIRONMENT'
DATA_CENTER_KEY='DATA_CENTER'
REMOTE_DATA_CENTER_KEY='REMOTE_DATA_CENTER'
APPLICATION_KEY='APPLICATION'
STRIPE_KEY='STRIPE'
INSTANCE_KEY='INSTANCE'


_REMOTE_DATA_CENTERS = {'AM1': 'AM2', 'AM2': 'AM1', 'AW1': 'AW2', 'AW2': 'AW1', 'EM1': 'EM2', 'EM2': 'EM1', 'AP1': 'AP2', 'AP2': 'AP1'}


def _build_properties_from_files(properties, filenames, common_directory):
    if isinstance(filenames, str):
        filenames = [filenames]

    for filename in reversed(filenames):
        properties.merge_with(Properties().build_from_file(os.path.join(common_directory, filename)))


class Deployment(object):
    def __init__(self, **kwargs):
        from .commands.builder import Builder

        properties = Properties()
        self._common_dir = kwargs.get('common_dir', os.path.join('common', kwargs['environment'], kwargs['data_center']))
        _build_properties_from_files(properties,
                kwargs.get('properties', "%s.properties" % kwargs['application']), self.common_directory)
        properties.save(ENVIRONMENT_KEY, kwargs['environment'], behavior=RAISE_ON_EXISTING)
        properties.save(DATA_CENTER_KEY, kwargs['data_center'], behavior=RAISE_ON_EXISTING)
        properties.save(REMOTE_DATA_CENTER_KEY, _REMOTE_DATA_CENTERS[kwargs['data_center']], behavior=RAISE_ON_EXISTING)
        properties.save(APPLICATION_KEY, kwargs['application'], behavior=RAISE_ON_EXISTING)
        properties.save(STRIPE_KEY, kwargs['stripe'], behavior=RAISE_ON_EXISTING)
        properties.save(INSTANCE_KEY, kwargs['instance'], behavior=RAISE_ON_EXISTING)
        self._overrides_dir = kwargs.get('overrides_dir', os.path.join('overrides', kwargs['application'], kwargs['stripe'], kwargs['instance']))
        self._builders = []
        for builder in kwargs.get('builders', []):
            if not isinstance(builder, Builder):
                raise TypeError("Any builder must inherit from Builder")
            self._builders.append(builder)
            builder.build_properties(properties)
        self._properties = properties

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
        return os.path.join(os.path.abspath(os.getcwd()), "deployments", self.environment, self.data_center, self.application, self.stripe, self.instance)

    def _log_configuration(self, msg):
        logger.debug("%s: %s", msg, str(self._configuration))

    @property
    def configuration(self):
        if not hasattr(self, '_configuration'):
            self._configuration = Configuration({'appName': self.stripe})
            self._log_configuration("Initial configration")
            for filename in [os.path.join(self.common_directory, 'common_params.json'), os.path.join(self.overrides_directory, 'app_params.json')]:
                try:
                    with open(filename, 'r') as json_file:
                        self._configuration = self._configuration.merge_with(json.load(json_file))
                except FileNotFoundError:
                    logger.info("Skipping %s since it cannot be found.", filename)
                self._log_configuration("After %s" % filename)
            self._configuration = self._configuration.apply_properties(self.properties)
            self._log_configuration("After applying properties")
        return self._configuration

    def create(self):
        self._clean_output_directory()
        for builder in self._builders:
            builder.build(self)
            builder.write_to_file(self)
        self._copy_instance_files()
        self._copy_common_files()

    def _clean_output_directory(self):
        if os.path.isdir(self.output_directory):
            shutil.rmtree(self.output_directory)

    def _copy_instance_files(self):
        self._copy_files(self.overrides_directory, ignore=shutil.ignore_patterns('app_params.json', '.*'))

    def _copy_common_files(self):
        self._copy_files(self.common_directory, ignore=shutil.ignore_patterns('common_params.json', '*.properties', '.*'))

    def _copy_files(self, source, ignore):
        if os.path.isdir(source):
            copytree(source, self.output_directory, ignore=ignore, copy_function=self._copy_file)

    def _copy_file(self, source, destination):
        with open(source, 'r') as src, open(destination, 'w') as dst:
            line_no = 1
            for line in src:
                try:
                    dst.write(self.properties.apply_to_value(line))
                    line_no += 1
                except KeyError:
                    logger.error("Failed to copy %s to %s", source, destination)
                    logger.exception("Failed while applying properties to line %d\n\t%s", line_no, line)
                    raise
