import copy


DEFAULT_START_SCRIPT_FILENAME = 'start_app.sh'


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
        return result

    def apply_properties(self, properties):
        result = self.__class__(self)
        _apply_properties_to_dict(result, properties)
        return result

    @property
    def application_type(self):
        return self['appType']

    @property
    def start_script_filename(self):
        return self.get('start_script_filename', DEFAULT_START_SCRIPT_FILENAME)


__all__ = ['DEFAULT_START_SCRIPT_FILENAME', 'Configuration']
