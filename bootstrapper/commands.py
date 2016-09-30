from abc import ABCMeta, abstractmethod
import os


class CommandBuilder(metaclass=ABCMeta):
    def __str__(self):
        return "%s%s" % (self.command, self._result)

    @property
    @abstractmethod
    def command(self):
        raise NotImplemented()

    def build(self, deployment):
        self._result = ""
        self.do_build(deployment)
        return self

    @abstractmethod
    def do_build(self, deployment):
        raise NotImplemented()

    def add_argument(self, string_format, *format_values):
        self._result += " \\\n\t" + (string_format % format_values)


class JavaCommandBuilder(CommandBuilder):
    @property
    def command(self):
        return "java"

    def do_build(self, deployment):
        configuration = deployment.get_jvm_configuration()
        self._build_memory_arguments(configuration.min_heap, configuration.max_heap)
        self._build_base_jvm_arguments(configuration.base_jvm_configuration)
        self._build_platform_arguments(configuration.platform_configuration)
        self._build_text_admin_argument(configuration.text_admin_port)
        self._build_connection_arguments(configuration.connection_configuration)
        self._build_udp_log_arguments(configuration.udp_log_configuration)
        self._build_remote_debug_arguments(configuration.remote_debug_configuration)
        self._build_package_scanner_argument()
        self._build_application_name_argument(configuration.application_name)
        return self


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
        self.add_argument("-Dtextadmin.listenPort=%d", text_admin_port)

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
                    udp_log_configuration['target'], udp_log_configuration['port'])
        else:
            self.add_argument("-Dmain.log.udp=false")

    def _build_remote_debug_arguments(self, remote_debug_configuration):
        if remote_debug_configuration:
            self.add_argument("%s,address=%d", remote_debug_configuration['args'], remote_debug_configuration['port'])

    def _build_package_scanner_argument(self):
        self.add_argument("-DPackageScanner.ignoreManifest=true")

    def _build_application_name_argument(self, application_name):
        self.add_argument("-DprocessName=%s", application_name)
        self.add_argument('-cp "libs/*"')
        self.add_argument("com.redi.platform.launcher.application.LauncherMain")
        self.add_argument("%s.commands", application_name)


class DockerCommandBuilder(CommandBuilder):
    def __init__(self, image, version=''):
        self._image = image
        self._version = version

    @property
    def image(self):
        return self._image

    @property
    def version(self):
        return self._version

    @property
    def command(self):
        return "docker run"

    def do_build(self, deployment):
        configuration = deployment.get_docker_container_configuration()
        self._build_working_directory(deployment.stripe, deployment.application, deployment.instance)
        self._build_image_name(deployment.stripe, deployment.application, deployment.instance)
        self._build_ports(deployment.ports)
        self._build_volumes(deployment.volumes)
        self._build_image()

    def _build_working_directory(self, stripe, application, instance):
        self.add_argument("--workdir %s", os.join("var", "redi", "runtime", application, stripe, instance))

    def _build_image_name(self, stripe, application, instance):
        self.add_argument("--name %s-%s-%s", stripe, application, instance)
        self.add_argument("--restart always")

    def _build_ports(self, ports):
        for port in ports:
            if isinstance(port, dict):
                self.add_argument("--publish %d:%d", port['host'], port['container'])
            else:
                self.add_argument("--publish %d", port)

    def _build_volumes(self, volumes):
        for volume in volumes:
            self.add_argument("--volume %s:%s", volume['host'], volume['container'])

    def _build_image(self):
        if self.version:
            self.add_argument("%s:%s", self.image, self.version)
        else:
            self.add_argument(self.image)


if __name__ == "__main__":
    from configuration import Configuration
    javaBuilder = JavaCommandBuilder()
    configuration = Configuration({'vmArgs': {'remoteDebug': {'args': '-agentlib:jdwp=transport=dt_socket,server=y,suspend=n', 'enabled': True}, 'connections': {'status': 'pulse://239.100.103.13:18013?ifName=lo', 'discovery': 'discovery://239.100.103.14:18014?ifName=lo'}, 'textAdmin': 1501, 'log': {'syslog': {'enabled': False}, 'udp': {'enabled': 'True', 'target': '10.160.10.182', 'port': 9475}, 'console': {'enabled': True}, 'file': {'enabled': False, 'target': 'messages.log'}}, 'platform': {'logPath': 'logs', 'configPath': 'config', 'dataPath': 'data'}, 'appName': 'OMS01-enrichment-agent', 'memory': {'minHeap': '2g', 'maxHeap': '3g'}, 'baseArgs': ['-server', '-XX:+UseCompressedOops', '-XX:+UseG1GC', '-XX:MaxGCPauseMillis=100', '-verbose:gc']}})
    javaBuilder.build(configuration)
    print(javaBuilder)
