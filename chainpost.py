import chainclient
import logging
from time import time
import datetime
import traceback

default_units = dict(
    temperature='celsius',
    humidity='percent',
    illuminance='lux',
    audio_level='dBFS',
)

class ChainPoster:

    def __init__(self, site_url, auth=None, debug=False):
        self.site_url = site_url
        self.backoff = 60.0
        self.last_failure = 0.0
        self.site = None
        self.log = logging.getLogger("poster")
        self.auth = auth
        if debug:
            import coloredlogs
            coloredlogs.install(level=logging.DEBUG)
        logging.getLogger('requests').setLevel(logging.WARNING)
        self.connect()

    def connect(self):
        if self.site is not None:
            return True # already 'connected'
        if time() - self.last_failure < self.backoff:
            return False
        self.log.info("Connecting")
        try:
            self.site = chainclient.get(self.site_url, auth=self.auth)
            self.devices_coll = self.site.rels['ch:devices']
            self.devices = {}
            for device in self.devices_coll.rels['items']:
                self.devices[device.name] = device
        except chainclient.ConnectionError as e:
            self.site = None
            self.log.error("Connecting to Chain API: %s", str(e))
            return False
        return True

    def reset(self):
        self.site = None
        self.devices = {}
        self.devices_coll = None
        self.last_failure = time()

    def get_device(self, name):
        try:
            dev = self.devices[name]
        except KeyError:
            self.log.info("Creating device %s", name)
            dev = self.devices_coll.create(dict(name=name), auth=self.auth)
            self.devices[name] = dev
        return dev

    def find_sensor(self, dev_name, metric, unit=None):
        dev = self.get_device(dev_name)
        #print type(dev)
        #print dev
        sensor_coll = dev.rels['ch:sensors']
        #print type(sensor_coll)
        sensor = None
        for s in sensor_coll.rels['items']:
            if s['metric'] == metric:
                sensor = s
                break
        if sensor is None:
            self.log.info("Creating sensor %s on device %s", metric, dev_name)
            if unit is None:
                unit = self.lookup_unit_by_metric(metric)
            sensor = sensor_coll.create(dict(metric=metric, unit=unit), auth=self.auth)
        return sensor

    def post_data(self, dev_name, metric, value, unit=None, timestamp=None, tzoffset=None):
        if not self.connect():
            self.log.warning("Dropping %s sample for sensor %s due to connection failure",
                metric, dev_name)
            return False
        try:
            if timestamp is None:
                timestamp = datetime.datetime.utcnow()
                tzoffset = "+00:00"
            sensor = self.find_sensor(dev_name, metric, unit)

            if tzoffset is not None:
                ts_str = timestamp.isoformat() + tzoffset
            else:
                ts_str = timestamp.isoformat()

            sensor_data = dict(
                value=value,
                timestamp=ts_str
            )
            history = sensor.rels['ch:dataHistory']
            self.log.debug("Posting %s data for sensor %s: %f", metric, dev_name, value)
            history.create(sensor_data, cache=False, auth=self.auth)
        except chainclient.ConnectionError as e:
            self.reset()
            self.log.error("Connection failure: %s", str(e))
            return False
        except Exception as e:
            self.log.exception("Unhandled %s exception while posting data: %s", repr(e), str(e))
            self.log.exception(traceback.format_exc())
            return False
        return True

    def post_multiple(self, dev_name, metric, values, unit=None, tzoffset=None):
        if not self.connect():
            self.log.warning("Dropping %s samples for sensor %s due to connection failure",
                metric, dev_name)
            return False
        try:
            sensor = self.find_sensor(dev_name, metric, unit)


            request = []
            for ts, val in values:
                if tzoffset is not None:
                    ts_str = ts.isoformat() + tzoffset
                else:
                    ts_str = ts.isoformat()

                sensor_data = dict(
                    value=val,
                    timestamp=ts_str
                )
                request.append(sensor_data)

            history = sensor.rels['ch:dataHistory']
            self.log.debug("Posting %d points of %s data for sensor %s", 
                len(request), metric, dev_name)
            history.create(request, cache=False, auth=self.auth)
        except chainclient.ConnectionError as e:
            self.reset()
            self.log.error("Connection failure: %s", str(e))
            return False
        except Exception as e:
            self.log.exception("Unhandled %s exception while posting data: %s", repr(e), str(e))
            self.log.exception(traceback.format_exc())
            return False
        return True
        


    def lookup_unit_by_metric(self, metric):
        return default_units.get(metric, "%s units" % metric)
