import socket
from . import logger


DATA_CENTER_TABLE = {
        'c1': 'AM1',
        's2': 'AM2',
        'a1': 'AW1',
        'a2': 'AW2',
        'l1': 'EM1',
        'l2': 'EM2',
        'h1': 'AP1',
        'h2': 'AP2' }

AVAILABILITY_ZONE_TABLE = {
        'a': 'A',
        'b': 'B' }

SECURITY_ZONE_TABLE = {
        'i': 'IDMZ',
        'z': 'DMZ',
        'b': 'Back End' }

OS_TABLE = {
        'c': 'centos',
        'w': 'Windows' }

ENVIRONMENT_TABLE = {
        'd': 'dev',
        't': 'qa',
        'p': 'prod' }


def _validate_args(kwargs):
    for key in kwargs.keys():
        if key not in ['hostname', 'data_center', 'availabilty_zone', 'security_zone', 'os', 'environment']:
            raise Exception("%s is an invalid setting for a location" % key)
    if 'hostname' in kwargs and \
            ('data_center' in kwargs or 'environment' in kwargs):
        raise Exception("hostname cannot appear with any other location argument")
    elif 'hostname' not in kwargs:
        if 'data_center' not in kwargs:
            raise Exception("Location needs a data_center")
        elif 'environment' not in kwargs:
            raise Exception("Location needs a environment")


def _safe_get_value(key, table, hostname, setting):
    try:
        return table[key]
    except KeyError:
        logger.exception("Failed to set %s from hostname '%s' because '%s' is not a valid value.", setting, hostname, key), "Valid values are:", "[%s]" % ", ".join(table.keys())
        raise


class Location(object):
    def __init__(self, **kwargs):
        if not kwargs:
            kwargs['hostname'] = socket.getfqdn()
        _validate_args(kwargs)
        self._hostname = kwargs.get('hostname', '')
        if self.hostname:
            self._data_center = _safe_get_value(self.hostname[0:2], DATA_CENTER_TABLE, self.hostname, 'data_center')
            self._availabilty_zone = _safe_get_value(self.hostname[2], AVAILABILITY_ZONE_TABLE, self.hostname, 'availabilty_zone')
            self._security_zone = _safe_get_value(self.hostname[3], SECURITY_ZONE_TABLE, self.hostname, 'security_zone')
            self._os = _safe_get_value(self.hostname[4], OS_TABLE, self.hostname, 'os')
            self._environment = _safe_get_value(self.hostname[5], ENVIRONMENT_TABLE, self.hostname, 'environment')
        else:
            self._data_center = kwargs['data_center']
            self._availabilty_zone = kwargs.get('availabilty_zone', '')
            self._security_zone = kwargs.get('security_zone', '')
            self._os = kwargs.get('os', '')
            self._environment = kwargs['environment']

    def __str__(self):
        result = []
        result.append('"environment": "%s"' % self.environment)
        result.append('"data_center": "%s"' % self.data_center)
        if self.availabilty_zone:
            result.append('"availabilty_zone": "%s"' % self.availabilty_zone)
        if self.security_zone:
            result.append('"security_zone": "%s"' % self.security_zone)
        if self.os:
            result.append('"os": "%s"' % self.os)
        if self.hostname:
            result.append('"hostname": "%s"' % self.hostname)
        return "{%s}" % ", ".join(result)

    @property
    def hostname(self):
        return self._hostname

    @property
    def data_center(self):
        return self._data_center

    @property
    def availabilty_zone(self):
        return self._availabilty_zone

    @property
    def security_zone(self):
        return self._security_zone

    @property
    def os(self):
        return self._os

    @property
    def environment(self):
        return self._environment


__all__ = ['DATA_CENTER_TABLE', 'AVAILABILITY_ZONE_TABLE', 'SECURITY_ZONE_TABLE', 'OS_TABLE', 'ENVIRONMENT_TABLE', 'Location']
