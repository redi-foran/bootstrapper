import os
import re


def _is_set(behavior, bit):
    return (behavior & bit) > 0


_parameter_expansion = re.compile(r"\\{0}\$\{([^$}]+)\}")


INSERT = 1
UPDATE = 2
UPSERT = 3
RAISE_ON_EXISTING = 4



class Properties(dict):
    def build_from_file(self, filename, behavior=UPSERT):
        with open(filename, 'r') as f:
            for line in f:
                (name, value) = self._parse_name_value(line)
                if (name is not None) and (value is not None):
                    self.save(name, value, behavior)
        return self

    def merge_with(self, properties, behavior=UPSERT):
        for name, value in properties.items():
            self.save(name, value, behavior)
        return self

    def save(self, name, value, behavior=UPSERT):
        if (name in self) and _is_set(behavior, RAISE_ON_EXISTING):
            raise LookupError("Cannot override '%s' with '%s' (already set to '%s')." %
                    (name, value, self[name]))
        else:
            behavior = INSERT

        if (name not in self) and _is_set(behavior, INSERT):
            self[name] = value
        elif (name in self) and _is_set(behavior, UPDATE):
            self[name] = value

        return self

    def _parse_name_value(self, line):
        equal_sign_location = line.find('=')
        if equal_sign_location > 0:
            name = line[:equal_sign_location].strip()
            value = line[equal_sign_location+1:].strip()
            return (name, value)
        return (None, None)

    def apply_to_value(self, value):
        if not isinstance(value, str):
            return value

        while True:
            parameter = _parameter_expansion.search(value)
            if parameter:
                value = value[:parameter.start()] + self[parameter.group(1).strip()] + value[parameter.end():]
            else:
                return value

    def apply_to_file(self, filename):
        template_contents = self._get_template_content(filename)
        self._remove_template_file(filename)
        self._write_expanded_content_back_to_file(template_contents, filename)

    def _get_template_content(self, filename):
        lines = []
        with open(filename, 'r') as f:
            for line in f:
                lines.append(line)
        return lines

    def _remove_template_file(self, filename):
        os.remove(filename)

    def _write_expanded_content_back_to_file(self, template_contents, filename):
        with open(filename, 'w') as f:
            for line in template_contents:
                f.write('%s' % self.apply_to_value(line))


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

MC_REGION_KEY = "MC_REGION"
MC_DATA_CENTER_KEY = "MC_DATA_CENTER"
MC_ENVIRONMENT_KEY = "MC_ENVIRONMENT"
MC_APPLICATION_ID_KEY = "MC_APPLICATION_ID"
MC_UPSTREAM_KEY = "MC_UPSTREAM"
MC_DOWNSTREAM_KEY = "MC_DOWNSTREAM"
MC_STATUS_KEY = "MC_STATUS"
MC_DISCOVERY_KEY = "MC_DISCOVERY"


def generate_properties_for_stream(deployment, application_id):
    if not isinstance(application_id, int):
        raise TypeError("application_id must be an integer")
    elif (0 < application_id) and (application_id <= 25):
        raise ValueError("application_id %d is not in range (0, 25]" % application_id)
    properties = Properties()
    properties.save(MC_UPSTREAM_KEY, "239.${%s}.${%s}${%s}.${%s}1" %
            (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY), behavior=RAISE_ON_EXISTING)
    properties.save(MC_DOWNSTREAM_KEY, "239.${%s}.${%s}${%s}.${%s}2" %
            (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY), behavior=RAISE_ON_EXISTING)
    properties.save(MC_STATUS_KEY, "239.${%s}.${%s}${%s}.${%s}3" %
            (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY), behavior=RAISE_ON_EXISTING)
    properties.save(MC_DISCOVERY_KEY, "239.${%s}.${%s}${%s}.${%s}4" %
            (MC_REGION_KEY, MC_DATA_CENTER_KEY, MC_ENVIRONMENT_KEY, MC_APPLICATION_ID_KEY), behavior=RAISE_ON_EXISTING)
    properties.save(MC_REGION_KEY, _MC_LOCATIONS[deployment.data_center][0], behavior=RAISE_ON_EXISTING)
    properties.save(MC_DATA_CENTER_KEY, _MC_LOCATIONS[deployment.data_center][1], behavior=RAISE_ON_EXISTING)
    properties.save(MC_ENVIRONMENT_KEY, _MC_ENVIRONMENTS[deployment.environment], behavior=RAISE_ON_EXISTING)
    properties.save(MC_APPLICATION_ID_KEY, application_id, behavior=RAISE_ON_EXISTING)
    deployment.properties.merge_with(properties, behavior=INSERT)


if __name__ == "__main__":
    import shutil
    shutil.copyfile('sequencer/sequencer.commands', 'sequencer/test.commands')
    properties = Properties()
    properties.build_from_file('environments/dev/AM3/HTA3.properties')
    properties.apply_to_file('sequencer/test.commands')
    print(properties)
