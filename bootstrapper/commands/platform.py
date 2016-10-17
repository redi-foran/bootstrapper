from .builder import CommandBuilder, Builder
from bootstrapper.properties import *
from bootstrapper.deployment import *


class PlatformJvmConfiguration(object):
    def __init__(self, configuration):
        self._configuration = configuration

    @property
    def vm_configuration(self):
        return self._configuration.get('vmArgs', {})

    @property
    def base_jvm_configuration(self):
        return self.vm_configuration.get('baseArgs', [])

    @property
    def _memory(self):
        return self._configuration.get('memory', {})

    @property
    def min_heap(self):
        return self._memory.get('min')

    @property
    def max_heap(self):
        return self._memory.get('max')

    @property
    def connection_configuration(self):
        return self.vm_configuration.get('connections', {})

    @property
    def platform_configuration(self):
        return self.vm_configuration.get('platform', {})

    @property
    def udp_log_configuration(self):
        udp_config = self.vm_configuration.get('log', {}).get('udp', {})
        if udp_config.get('enabled', False):
            return {'target': udp_config['target'], 'port': int(udp_config['port'])}
        return {}

    @property
    def text_admin_port(self):
        return int(self.vm_configuration.get('textAdmin', 0))

    @property
    def remote_debug_configuration(self):
        remote_debug_config = self.vm_configuration.get('remoteDebug', {})
        if remote_debug_config.get('enabled', False):
            return {'args': remote_debug_config['args'], 'port': int(remote_debug_config.get('port', self.text_admin_port + 1000))}
        return {}

    @property
    def config_directory(self):
        return self.platform_configuration.get('configPath', 'config')


def _invalidate_application_id(application_id):
    if application_id is None:
        raise ValueError("'%s' property must be defined for a platform application." % MC_APPLICATION_ID_KEY)
    elif not application_id.isdigit():
        raise TypeError("%s (%s) must be a positive integer" % (MC_APPLICATION_ID_KEY, application_id))
    else:
        application_id = int(application_id)
        if not ((0 < application_id) and (application_id <= 25)):
            raise ValueError("application_id %d is not in range (0, 25]" % application_id)


_MC_LOCATIONS = {
        'AM1': (100, 12),
        'AM2': (100, 10),
        'AW1': (100, 13),
        'AW2': (100, 14),
        'EM1': (102, 10),
        'EM2': (102, 11),
        'AP1': (104, 10),
        'AP2': (104, 11)
        }
_MC_ENVIRONMENTS = {
        'prod': 0,
        'uat': 1,
        'qa': 2,
        'dev': 3
        }


def _write_line_to_file(line, output_file, properties):
    output_file.write(properties.apply_to_value(line))


class StreamBuilder(Builder):
    def build_properties(self, properties):
        _invalidate_application_id(properties.get(MC_APPLICATION_ID_KEY))

        properties.save(MC_UPSTREAM_PORT_KEY, 15000, behavior=INSERT)
        properties.save(MC_UPSTREAM_IFNAME_KEY, "${%s}" % MC_NETWORK_DEVICE_KEY, behavior=INSERT)
        properties.save(MC_UPSTREAM_KEY, "blah://239.${%s}.${%s}${%s}.${%s}1:${%s}?ifName=${%s}" %
                (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY, MC_UPSTREAM_PORT_KEY, MC_UPSTREAM_IFNAME_KEY), behavior=INSERT)

        properties.save(MC_DOWNSTREAM_PORT_KEY, 15001, behavior=INSERT)
        properties.save(MC_DOWNSTREAM_IFNAME_KEY, "${%s}" % MC_NETWORK_DEVICE_KEY, behavior=INSERT)
        properties.save(MC_DOWNSTREAM_KEY, "blast://239.${%s}.${%s}${%s}.${%s}2:${%s}?ifName=${%s}" %
                (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY, MC_DOWNSTREAM_PORT_KEY, MC_DOWNSTREAM_IFNAME_KEY), behavior=INSERT)

        properties.save(MC_STATUS_PORT_KEY, 15002, behavior=INSERT)
        properties.save(MC_STATUS_IFNAME_KEY, "${%s}" % MC_NETWORK_DEVICE_KEY, behavior=INSERT)
        properties.save(MC_STATUS_KEY, "pulse://239.${%s}.${%s}${%s}.${%s}3:${%s}?ifName=${%s}" %
                (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY, MC_STATUS_PORT_KEY, MC_STATUS_IFNAME_KEY), behavior=INSERT)

        properties.save(MC_DISCOVERY_PORT_KEY, 15003, behavior=INSERT)
        properties.save(MC_DISCOVERY_IFNAME_KEY, "${%s}" % MC_NETWORK_DEVICE_KEY, behavior=INSERT)
        properties.save(MC_DISCOVERY_KEY, "discovery://239.${%s}.${%s}${%s}.${%s}4:${%s}?ifName=${%s}" %
                (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY, MC_DISCOVERY_PORT_KEY, MC_DISCOVERY_IFNAME_KEY), behavior=INSERT)

        properties.save(MC_REGION_KEY, _MC_LOCATIONS[properties[DATA_CENTER_KEY]][0], behavior=INSERT)
        properties.save(MC_DATA_CENTER_KEY, _MC_LOCATIONS[properties[DATA_CENTER_KEY]][1], behavior=INSERT)
        properties.save(MC_ENVIRONMENT_KEY, _MC_ENVIRONMENTS[properties[ENVIRONMENT_KEY]], behavior=INSERT)

    def build(self, deployment):
        pass

    def write_to_file(self, deployment):
        lines = self._get_lines()
        if lines:
            configuration = PlatformJvmConfiguration(deployment.configuration)
            config_directory = os.path.join(deployment.output_directory, configuration.config_directory)
            if not os.path.isdir(config_directory):
                os.makedirs(config_directory)
            with open(os.path.join(config_directory, self._get_filename(deployment)), 'w') as stream_file:
                _write_line_to_file(lines[0], stream_file, deployment.properties)
                for line in lines[1:]:
                    stream_file.write('\n')
                    _write_line_to_file(line, stream_file, deployment.properties)

    def _get_lines(self):
        return []

    def _get_filename(self, deployment):
        return "%s.commands" % deployment.stripe


class StreamFileBuilder(StreamBuilder):
    def _get_lines(self):
        lines = []
        lines.append('setUpstreamConnection URL="${%s}"' % MC_UPSTREAM_KEY)
        lines.append('setDownstreamConnection URL="${%s}"' % MC_DOWNSTREAM_KEY)
        lines.append('setRecoveryConnection NAME="APP-REWIND" URL="auto://app-rewind"')
        return lines

    def _get_filename(self, deployment):
        return "%s.stream" % deployment.application


class SequencerCommandsFileBuilder(StreamBuilder):
    def __init__(self, sequencer_type='sequencer'):
        self._sequencer_type = sequencer_type

    def _get_lines(self):
        lines = []
        lines.append('/launch TYPE=%s INSTANCE=SEQUENCER' % self._sequencer_type)
        lines.append('/SEQUENCER/start URL="stream://${%s}" STREAM-ID="${%s}"' % (APPLICATION_KEY, APPLICATION_KEY))
        lines.append('/SEQUENCER/addServer NAME="DOWNSTREAM_MULTICAST" URL="${%s}"' % MC_DOWNSTREAM_KEY)
        lines.append('/SEQUENCER/addServer NAME="UPSTREAM_MULTICAST" URL="${%s}"' % MC_UPSTREAM_KEY)
        lines.append('/SEQUENCER/addServer NAME="SEQUENCER_REWIND" URL="beam://0.0.0.0:18000?discoveryId=sequencer-rewind"')
        return lines


class CommanderCommandsFileBuilder(StreamBuilder):
    def __init__(self, commander_type='commander'):
        self._commander_type = commander_type

    def _get_lines(self):
        lines = []
        lines.append('/launch TYPE=%s INSTANCE=COMMANDER' % self._commander_type)
        lines.append('/COMMANDER/start URL="stream://${%s}" STREAM-ID="${%s}"' % (APPLICATION_KEY, APPLICATION_KEY))
        lines.append('/COMMANDER/addStartOfSessionCommand DISCOVERY-ID="activatable_component" ACTIVE=false PRIMARY=true COMMAND=setActive CRITICAL=true')
        lines.append('/services/bus/start URL="stream://${%s}"' % APPLICATION_KEY)
        return lines


class PlatformCommandBuilder(CommandBuilder, StreamBuilder):
    def __init__(self, text_admin_port=0):
        if text_admin_port < 0:
            raise ValueError("Text admin port %d must be a positive integer" % text_admin_port)
        self._text_admin_port = text_admin_port

    @property
    def executable(self):
        return "java"

    def do_build(self, deployment):
        configuration = PlatformJvmConfiguration(deployment.configuration)
        self._build_memory_arguments(configuration.min_heap, configuration.max_heap)
        self._build_base_jvm_arguments(configuration.base_jvm_configuration)
        self._build_platform_arguments(configuration.platform_configuration)
        self._build_text_admin_argument(configuration.text_admin_port)
        self._build_connection_arguments(configuration.connection_configuration)
        self._build_udp_log_arguments(configuration.udp_log_configuration)
        self._build_remote_debug_arguments(configuration.remote_debug_configuration)
        self._build_package_scanner_argument()
        self._build_application_name_argument(deployment.stripe)

    def write_to_file(self, deployment):
        self._write_to_file(deployment, "echo -n 'Current directory is: '", "pwd", "ls *")

    def _build_memory_arguments(self, min_heap, max_heap):
        if min_heap:
            self.add_argument("-Xms%s", min_heap)
        if max_heap:
            self.add_argument("-Xmx%s", max_heap)

    def _build_base_jvm_arguments(self, base_jvm_configuration):
        for jvm_argument in base_jvm_configuration:
            self.add_argument(jvm_argument)

    def _build_platform_arguments(self, platform_configuration):
        for key in sorted(platform_configuration.keys()):
            self.add_argument("-Dplatform.%s=%s", str(key), str(platform_configuration[key]))

    def _build_text_admin_argument(self, text_admin_port):
        if (text_admin_port > 0) and (self._text_admin_port > 0):
            if text_admin_port == self._text_admin_port:
                logger.warning("Text admin port specified in platform command builder and in configuration file(s).")
        elif self._text_admin_port > 0:
            text_admin_port = self._text_admin_port

        if text_admin_port > 0:
            self.add_argument("-Dtextadmin.listenPort=%d", text_admin_port)
        elif text_admin_port < 0:
            raise ValueError("Text admin port %d must be a positive integer" % text_admin_port)
        elif text_admin_port == 0:
            raise ValueError("Text admin port was not properly specified (must be a positive integer)")

    def _build_connection_argument(self, configuration, connectionName, argument):
        value = configuration.get(connectionName)
        if value:
            self.add_argument("-D%s=%s", str(argument), str(value))

    def _build_connection_arguments(self, connection_configuration):
        self._build_connection_argument(connection_configuration, "discovery", "discoveryUrl")
        self._build_connection_argument(connection_configuration, "status", "status.target")

    def _build_udp_log_arguments(self, udp_log_configuration):
        if udp_log_configuration:
            self.add_argument("-Dmain.log.udp=true -Dudp.log.target=%s -Dudp.log.port=%d",
                    udp_log_configuration['target'], int(udp_log_configuration['port']))
        else:
            self.add_argument("-Dmain.log.udp=false")

    def _build_remote_debug_arguments(self, remote_debug_configuration):
        if remote_debug_configuration:
            self.add_argument("%s,address=%d", remote_debug_configuration['args'], int(remote_debug_configuration['port']))

    def _build_package_scanner_argument(self):
        self.add_argument("-DPackageScanner.ignoreManifest=true")

    def _build_application_name_argument(self, application_name):
        self.add_argument("-DprocessName=%s", application_name)
        self.add_argument('-cp \\"libs/*\\"')
        self.add_argument("com.redi.platform.launcher.application.LauncherMain")
        self.add_argument("%s.commands", application_name)

    def execute(self, runner):
        return self._do_execute(self.command)
