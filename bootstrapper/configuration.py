import copy


_DEFAULT_PLATFORM_START_SCRIPT_FILENAME = 'start_platform_jvm.sh'


def _apply_properties_to_dict(result, properties):
    for (name, value) in result.items():
        name = _clean_name(name, result, properties)
        value = _clean_value(value, properties)
        result[name] = value


def _clean_name(name, result, properties):
    if name != properties.apply_to_value(name):
        del result[name]
        return properties.apply_to_value(name)
    return name


def _clean_value(value, properties):
    if isinstance(value, dict):
        return _clean_dict(value, properties)
    elif isinstance(value, list):
        return _clean_list(value, properties)
    else:
        return properties.apply_to_value(value)


def _clean_dict(value, properties):
    _apply_properties_to_dict(value, properties)
    return value


def _clean_list(values, properties):
    return [_clean_value(value, properties) for value in values]


def _merge_dict(result, other):
    if result is None or other is None:
        return

    for key2, val2 in other.items():
        if key2 in result:
            val1 = result[key2]
            if not isinstance(val1, list) and not isinstance(val1, dict):
                result[key2] = str(val2)
            elif isinstance(val1, list) and isinstance(val1, list):
                result[key2] = val1 + val2
            else:
                _merge_dict(val1, val2)
        else:
            result[key2] = val2


class Configuration(dict):
    def __init__(self, config={}):
        super(Configuration, self).__init__(copy.deepcopy(config))

    def merge_with(self, other):
        result = self.__class__(self)
        _merge_dict(result, other)
        result._remove_unwanted_settings()
        return result

    def apply_properties(self, properties):
        result = self.__class__(self)
        _apply_properties_to_dict(result, properties)
        return result

    def _remove_unwanted_settings(self):
        all_keys = self._get_known_keys()
        if not all_keys:
            return
        for key in self.keys():
            if key not in self._get_known_keys():
                del self[key]

    def _get_known_keys(self):
        return []


class PlatformJvmConfiguration(Configuration):
    @property
    def vm_configuration(self):
        return self['vmArgs']

    @property
    def base_jvm_configuration(self):
        return self.vm_configuration.get('baseArgs', [])

    @property
    def _memory(self):
        return self.vm_configuration.get('memory', {})

    @property
    def min_heap(self):
        return self._memory.get('minHeap')

    @property
    def max_heap(self):
        return self._memory.get('maxHeap')

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
        return int(self.vm_configuration['textAdmin'])

    @property
    def application_name(self):
        return self.vm_configuration['appName']

    @property
    def application_type(self):
        return self['appType']

    @property
    def remote_debug_configuration(self):
        remote_debug_config = self.vm_configuration.get('remoteDebug', {})
        if remote_debug_config.get('enabled', False):
            return {'args': remote_debug_config['args'], 'port': int(remote_debug_config.get('port', self.text_admin_port + 1000))}
        return {}

    @property
    def start_script_filename(self):
        return self.get('start_script_filename', _DEFAULT_PLATFORM_START_SCRIPT_FILENAME)

    def _get_known_keys(self):
        return ['vmArgs', 'appName', 'start_script_filename']


class DockerContainerConfiguration(Configuration):
    @property
    def _docker_container(self):
        return self.get('dockerContainer', {})

    @property
    def volumes(self):
        return self._docker_container.get('volumes', [])

    @property
    def ports(self):
        return self._docker_container.get('ports', [])

    @property
    def start_script_filename(self):
        return self.get('start_script_filename', _DEFAULT_PLATFORM_START_SCRIPT_FILENAME)

    def _get_known_keys(self):
        return ['dockerContainer', 'start_script_filename']


if __name__ == "__main__":
    from properties import *

    print("Problem 1: Simple merge")
    print(Configuration({'vmArgs': {'memory': {'max': '2g', 'min': '1g'}}}).merge_with({'vmArgs': {'memory': {'max': '3g', 'min': '2g'}}}))

    print("Problem 2: Partial merge")
    print(Configuration({'vmArgs': {'memory': {'max': '2g', 'min': '1g'}}}).merge_with({'vmArgs': {'memory': {'max': '3g'}}}))

    print("Problem 3: Insertion")
    print(Configuration({'vmArgs': {'memory': {'max': '2g', 'min': '1g'}}}).merge_with({'vmArgs': {'memory': {'max': '3g'}, 'log': {'udp': {'enabled': True}}}}))

    print("Problem 4: New")
    print(Configuration({}).merge_with({'vmArgs': {'memory': {'max': '3g'}, 'log': {'udp': {'enabled': True}}}}))

    print("Problem 5: Nothing to merge")
    print(Configuration({'vmArgs': {'memory': {'max': '3g'}, 'log': {'udp': {'enabled': True}}}}).merge_with({}))

    print("Problem 6: Applying properties to values")
    print(Configuration({'key': '${value}'}).apply_properties(Properties().save('key', 'AndrewKey').save('value', 'AndrewValue')))

    print("Problem 7: Applying properties to keys")
    print(Configuration({'${key}': 'value'}).apply_properties(Properties().save('key', 'AndrewKey').save('value', 'AndrewValue')))

    print("Problem 8: Applying properties to keys and values")
    print(Configuration({'${key}': '${value}'}).apply_properties(Properties().save('key', 'AndrewKey').save('value', 'AndrewValue')))
