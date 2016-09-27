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



if __name__ == "__main__":
    import shutil
    shutil.copyfile('sequencer/sequencer.commands', 'sequencer/test.commands')
    properties = Properties()
    properties.build_from_file('environments/dev/AM3/HTA3.properties')
    properties.apply_to_file('sequencer/test.commands')
    print(properties)
