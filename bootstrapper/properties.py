import os
import re


def _is_set(behavior, bit):
    return (behavior & bit) > 0


_parameter_expansion = re.compile(r"\\{0}\$\{([^$}]+)\}")


INSERT = 1
UPDATE = 2
UPSERT = 3
RAISE_ON_EXISTING = 4


MC_REGION_KEY = "MC_REGION"
MC_DATA_CENTER_KEY = "MC_DATA_CENTER"
MC_ENVIRONMENT_KEY = "MC_ENVIRONMENT"
MC_APPLICATION_ID_KEY = "MC_APPLICATION_ID"
MC_UPSTREAM_KEY = "MC_UPSTREAM"
MC_DOWNSTREAM_KEY = "MC_DOWNSTREAM"
MC_STATUS_KEY = "MC_STATUS"
MC_DISCOVERY_KEY = "MC_DISCOVERY"
MC_UPSTREAM_PORT_KEY = "MC_UPSTREAM_PORT"
MC_DOWNSTREAM_PORT_KEY = "MC_DOWNSTREAM_PORT"
MC_STATUS_PORT_KEY = "MC_STATUS_PORT"
MC_DISCOVERY_PORT_KEY = "MC_DISCOVERY_PORT"
MC_REWINDER_PORT_KEY = "MC_REWINDER_PORT"
MC_UPSTREAM_IFNAME_KEY = "MC_UPSTREAM_IFNAME"
MC_DOWNSTREAM_IFNAME_KEY = "MC_DOWNSTREAM_IFNAME"
MC_STATUS_IFNAME_KEY = "MC_STATUS_IFNAME"
MC_DISCOVERY_IFNAME_KEY = "MC_DISCOVERY_IFNAME"
MC_NETWORK_DEVICE_KEY = "MC_NETWORK_DEVICE"



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
                value = value[:parameter.start()] + str(self[parameter.group(1).strip()]) + value[parameter.end():]
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
