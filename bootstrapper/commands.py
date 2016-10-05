from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
import os
import stat
import subprocess
import shlex


@contextmanager
def run_in_directory(directory):
    current_directory = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(current_directory)


class CommandBuilder(metaclass=ABCMeta):
    def __str__(self):
        return self.command

    @property
    @abstractmethod
    def executable(self):
        raise NotImplemented()

    @property
    @abstractmethod
    def start_script_filename(self):
        raise NotImplemented()

    @property
    def command(self):
        return shlex.split(self.executable) + self._arguments

    def build(self, deployment, write_to_file=True):
        self._arguments = []
        self.do_build(deployment, write_to_file)
        return self

    @abstractmethod
    def do_build(self, deployment):
        raise NotImplemented()

    def add_argument(self, string_format, *format_values):
        self._arguments += [x.strip() for x in shlex.split(string_format % format_values) if len(x.strip()) > 0]

    def _write_script_to_file(self, deployment, script_filename, *extra_commands):
        scripts_directory = os.path.join(deployment.output_directory, 'scripts')
        script_filename = os.path.join(scripts_directory, script_filename)
        if not os.path.isdir(scripts_directory):
            os.makedirs(scripts_directory)
        with open(script_filename, 'w') as f:
            f.write('#!/bin/sh\n')
            for cmd in extra_commands:
                f.write("%s\n" % cmd)
            f.write(" \\n\t".join(self.command))
        os.chmod(script_filename, stat.S_IXUSR | os.stat(script_filename).st_mode)

    @abstractmethod
    def execute(self, runner):
        raise NotImplemented()

    def _do_execute(self, command):
        print("Running:", " ".join(command))
        return subprocess.run(command, stderr=subprocess.STDOUT)


class PlatformCommandBuilder(CommandBuilder):
    @property
    def executable(self):
        return "java"

    @property
    def start_script_filename(self):
        return self._start_script_filename

    def do_build(self, deployment, write_to_file):
        configuration = deployment.platform_configuration
        self._start_script_filename = configuration.start_script_filename
        self._build_memory_arguments(configuration.min_heap, configuration.max_heap)
        self._build_base_jvm_arguments(configuration.base_jvm_configuration)
        self._build_platform_arguments(configuration.platform_configuration)
        self._build_text_admin_argument(configuration.text_admin_port)
        self._build_connection_arguments(configuration.connection_configuration)
        self._build_udp_log_arguments(configuration.udp_log_configuration)
        self._build_remote_debug_arguments(configuration.remote_debug_configuration)
        self._build_package_scanner_argument()
        self._build_application_name_argument(configuration.application_name)
        if write_to_file:
            self._write_script_to_file(deployment, configuration.start_script_filename)


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

    def execute(self, runner):
        return self._do_execute(self.command)


class DockerCommandBuilder(CommandBuilder):
    @property
    def executable(self):
        return "docker run"

    @property
    def start_script_filename(self):
        return self._start_script_filename

    def do_build(self, deployment, write_to_file):
        configuration = deployment.docker_container_configuration
        self._start_script_filename = configuration.start_script_filename
        self._build_working_directory(deployment.run_directory)
        self._build_image_name(deployment.stripe, deployment.application, deployment.instance)
        self._build_ports(configuration.ports)
        self._build_volumes(configuration.volumes)

    def _build_working_directory(self, run_directory):
        index = run_directory.find(os.getcwd())
        if index >= 0:
            run_directory = run_directory[len(os.getcwd()):]
        self.add_argument("--workdir %s", run_directory)

    def _build_image_name(self, stripe, application, instance):
        self.add_argument("--rm")
        self.add_argument("--name %s-%s-%s", application, stripe, instance)

    def _build_ports(self, ports):
        for port in ports:
            if isinstance(port, dict):
                self.add_argument("--publish %d:%d", port['host'], port['container'])
            else:
                self.add_argument("--publish %d", port)

    def _build_volumes(self, volumes):
        for volume in volumes:
            self.add_argument("--volume %s:%s", volume['host'], volume['container'])

    def execute(self, runner):
        image = "%s:%s" % (runner.version_info['image_name'], runner.version_info['image_version'])
        self._pull_docker_image(image)
        with run_in_directory(runner.deployment.run_directory):
            return self._do_execute(self.command + [image, os.path.join('scripts', self.start_script_filename)])

    def _pull_docker_image(self, image):
        return subprocess.run(['docker', 'pull', image], stderr=subprocess.STDOUT)


if __name__ == "__main__":
    from configuration import Configuration
    javaBuilder = PlatformCommandBuilder()
    configuration = Configuration({'vmArgs': {'remoteDebug': {'args': '-agentlib:jdwp=transport=dt_socket,server=y,suspend=n', 'enabled': True}, 'connections': {'status': 'pulse://239.100.103.13:18013?ifName=lo', 'discovery': 'discovery://239.100.103.14:18014?ifName=lo'}, 'textAdmin': 1501, 'log': {'syslog': {'enabled': False}, 'udp': {'enabled': 'True', 'target': '10.160.10.182', 'port': 9475}, 'console': {'enabled': True}, 'file': {'enabled': False, 'target': 'messages.log'}}, 'platform': {'logPath': 'logs', 'configPath': 'config', 'dataPath': 'data'}, 'appName': 'OMS01-enrichment-agent', 'memory': {'minHeap': '2g', 'maxHeap': '3g'}, 'baseArgs': ['-server', '-XX:+UseCompressedOops', '-XX:+UseG1GC', '-XX:MaxGCPauseMillis=100', '-verbose:gc']}})
    javaBuilder.build(configuration)
    print(javaBuilder)
