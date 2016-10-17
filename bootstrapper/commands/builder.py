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


class Builder(object, metaclass=ABCMeta):
    def build_properties(self, properties):
        pass

    @abstractmethod
    def build(self, deployment):
        raise NotImplemented()

    @abstractmethod
    def write_to_file(self, deployment):
        raise NotImplemented()


class CommandBuilder(Builder, metaclass=ABCMeta):
    def __str__(self):
        return self.command

    @property
    @abstractmethod
    def executable(self):
        raise NotImplemented()

    @property
    def command(self):
        return shlex.split(self.executable) + self._arguments

    def build(self, deployment):
        self._arguments = []
        self.do_build(deployment)
        return self

    @abstractmethod
    def do_build(self, deployment):
        raise NotImplemented()

    def add_argument(self, string_format, *format_values):
        self._arguments += [x.strip() for x in shlex.split(string_format % format_values) if len(x.strip()) > 0]

    def write_to_file(self, deployment):
        self._write_to_file(deployment)

    def _write_to_file(self, deployment, *extra_commands):
        scripts_directory = os.path.join(deployment.output_directory, 'scripts')
        script_filename = os.path.join(scripts_directory, deployment.configuration.start_script_filename)
        if not os.path.isdir(scripts_directory):
            os.makedirs(scripts_directory)
        with open(script_filename, 'w') as f:
            f.write('#!/bin/sh\n')
            for cmd in extra_commands:
                f.write("%s\n" % cmd)
            cmd = " ".join(self.command)
            f.write('echo "%s"\n' % cmd.translate({'"': r'\"', '$': r'\$' }))
            f.write(cmd)
        os.chmod(script_filename, stat.S_IXUSR | os.stat(script_filename).st_mode)

    @abstractmethod
    def execute(self, runner):
        raise NotImplemented()

    def _do_execute(self, command):
        print("Running:", " ".join(command))
        return subprocess.run(command, stderr=subprocess.STDOUT)


if __name__ == "__main__":
    from configuration import Configuration
    javaBuilder = PlatformCommandBuilder()
    configuration = Configuration({'vmArgs': {'remoteDebug': {'args': '-agentlib:jdwp=transport=dt_socket,server=y,suspend=n', 'enabled': True}, 'connections': {'status': 'pulse://239.100.103.13:18013?ifName=lo', 'discovery': 'discovery://239.100.103.14:18014?ifName=lo'}, 'textAdmin': 1501, 'log': {'syslog': {'enabled': False}, 'udp': {'enabled': 'True', 'target': '10.160.10.182', 'port': 9475}, 'console': {'enabled': True}, 'file': {'enabled': False, 'target': 'messages.log'}}, 'platform': {'logPath': 'logs', 'configPath': 'config', 'dataPath': 'data'}, 'appName': 'OMS01-enrichment-agent', 'memory': {'minHeap': '2g', 'maxHeap': '3g'}, 'baseArgs': ['-server', '-XX:+UseCompressedOops', '-XX:+UseG1GC', '-XX:MaxGCPauseMillis=100', '-verbose:gc']}})
    javaBuilder.build(configuration)
    print(javaBuilder)
