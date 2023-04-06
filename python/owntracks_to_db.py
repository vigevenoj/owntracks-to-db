#! /usr/bin/env python
"""
Store owntracks location updates in a database
"""
from datetime import datetime, timezone
from pgdb import connect
from prometheus_client import start_http_server, Counter, Gauge
import argparse
import json
import logging
import logging.handlers
import os
import paho.mqtt.client as mqtt
import ssl
import time
import yaml


class OwntracksToDatabaseBridge():
    """
    Subscribe to owntracks updates and insert them into a postgres database
    """
    def __init__(self, configs):
        """
        Initialize our owntracks->db bridge from the configuration map, and
        connect to the MQTT broker and database
        """
        # Declare our metrics for later use
        self.total_recieved_updates = Counter(
            'total_received_updates',
            'The number of updates received from the mqtt broker')
        self.total_persisted_updates = Counter(
            'total_persisted_updates',
            'The number of updates saved into the database')
        self._last_persisted_timestamp = 0
        self._last_received_timestamp = 0
        self.persistance_lag = Gauge(
            'persistence_lag',
            'Seconds between most-recently-received update and ' +
            'the most-recently-persisted update')
        self.insertion_errors = Counter(
            'insertion_errors',
            'Count of errors inserting records into the database')
        self.current_insertion_errors = Gauge(
            'current_insertion_errors',
            'Number of insertion errors since successful insert into database')
        # Configure logging
        # This should probably just be stdout?
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(__name__)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        dbhost = configs['database']['host']
        dbport = configs['database']['port']
        dbuser = configs['database']['username']
        dbpass = configs['database']['password']
        dbname = configs['database']['dbname']

        # TODO: if connection to database fails, retry with backoff
        self._conn = connect(database=dbname, host=dbhost, port=dbport,
                             user=dbuser, password=dbpass)

        # Handle mqtt messages from the channels we subscribe to
        def handle_message(client, userdata, message):
            """
            Individual owntracks update messages are parsed for a username
            and a device name, and that information is used to insert the
            update into the database.
            """
            msg_json = json.loads(str(message.payload, encoding="ascii"))
            if(message.topic.startswith("owntracks")):
                # If message format is 'owntracks/user/device'
                # then we should try to parse out userid/deviceid
                # and handle this message as a location update
                if(msg_json['_type'] == 'location'):
                    userid = message.topic.split('/')[1]
                    device = message.topic.split('/')[2]
                    self._logger.info("{0} {1} posted an update: {2} with tst {3}"
                                      .format(userid, device, msg_json, msg_json['tst']))
                    self.total_recieved_updates.inc()
                    self.handle_location_update(userid, device, msg_json)
        self._client = mqtt.Client(client_id="")
        try:
            self._client.tls_set(ca_certs=configs['mqtt']['ca'],
                                 cert_reqs=ssl.CERT_REQUIRED,
                                 tls_version=ssl.PROTOCOL_TLSv1_2)
        except IOError as e:
            self._logger.error("Something went wrong in mqtt setup. {0}"
                               .format(e))
        self._client.username_pw_set(configs['mqtt']['username'],
                                     configs['mqtt']['password'])
        self._client.will_set("/lwt/o2db",
                              payload="o2db script offline")
        mqtt_host = configs['mqtt']['host']
        mqtt_port = configs['mqtt']['port']
        self._client.on_message = handle_message
        self._logger.warning("Connecting to mqtt at {0}:{1}...".format(
            mqtt_host, mqtt_port))
        # TODO: if connecting to mqtt broker fails, retry with backoff
        self._client.connect(mqtt_host, mqtt_port)
        self._logger.warning("owntracks to db bridge started successfully")

    def handle_location_update(self, user, device, rawdata):
        """
        Insert a location update into the database and increment any relevant
        counters. Update lag time between latest insertion and most recently
        received update
        """
        acc = rawdata.get('acc')  # accuracy in meters
        alt = rawdata.get('alt')  # altitude above sea level
        batt = rawdata.get('batt')  # battery percentage
        cog = rawdata.get('cog')  # course over ground
        lat = rawdata['lat']  # latitude
        lon = rawdata['lon']  # longitude
        rad = rawdata.get('rad')  # radius around region
        t = rawdata.get('t')  # p, c, b, r, u, t; see booklet
        tid = rawdata.get('tid')  # tracker ID
        tst = datetime.fromtimestamp(rawdata['tst'], timezone.utc)  # Timestamp
        vac = rawdata.get('vac')  # vertical accuracy
        vel = rawdata.get('vel')  # velocity, kmh
        pressure = rawdata.get('p')  # barometric pressure in kPa (float)
        connection_status = rawdata.get('conn')  # connection status: w, o, m

        # execute prepared statement
        try:
            cur = self._conn.cursor()
            cur.execute(
                """insert into locationupdates (acc, alt, batt, cog, lat, lon,
                radius, t, tid, tst, vac, vel, p, conn, rawdata, userid, device)
                values (%(acc)s, %(alt)s, %(batt)s, %(cog)s, %(lat)s, %(lon)s,
                %(rad)s, %(t)s, %(tid)s, %(tst)s, %(vac)s, %(vel)s, %(p)s,
                %(conn)s, %(rawdata)s, %(userid)s, %(device)s);""",
                {'acc': acc, 'alt': alt, 'batt': batt, 'cog': cog, 'lat': lat,
                 'lon': lon, 'rad': rad, 't': t, 'tid': tid, 'tst': tst,
                 'vac': vac, 'vel': vel, 'p': pressure,
                 'conn': connection_status, 'rawdata': json.dumps(rawdata),
                 'userid': user, 'device': device})
            self._conn.commit()
            self.total_persisted_updates.inc()
            self.current_insertion_errors.set(0)
        except Exception as e:
            # TODO We should try to persist this update again
            self.insertion_errors.inc()
            self.current_insertion_errors.inc()
            self._logger.error("Unable to execute query: {0}".format(e))

    def run(self):
        """
        Subscribe to the channel and loop until terminated
        """
        self._client.subscribe([("owntracks/#", 0)])
        self._logger.warning("subscribed to 'owntracks/#'")
        self._client.loop_forever()
        try:
            while True:
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            self._client.disconnect()


def handle_environment_configuration(configmap): # noqa: C901
    print("Overriding configuration file with environment configuration")
    base = 'OWNTRACKS2DB_'
    configmap = ensure_keys(configmap)

    if os.environ.get(base + 'MQTT_HOST'):
        configmap['mqtt']['host'] = os.environ[base + 'MQTT_HOST']
    if os.environ.get(base + 'MQTT_PORT'):
        configmap['mqtt']['port'] = int(os.environ[base + 'MQTT_PORT'])
    if os.environ.get(base + 'MQTT_SSL'):
        configmap['mqtt']['ssl'] = os.environ[base + 'MQTT_SSL']
    if os.environ.get(base + 'MQTT_CA'):
        configmap['mqtt']['ca'] = os.environ[base + 'MQTT_CA']
    if os.environ.get(base + 'MQTT_USERNAME'):
        configmap['mqtt']['username'] = os.environ[base + 'MQTT_USERNAME']
    if os.environ.get(base + 'MQTT_PASSWORD'):
        configmap['mqtt']['password'] = os.environ[base + 'MQTT_PASSWORD']
    if os.environ.get(base + 'DB_HOST'):
        configmap['database']['host'] = os.environ[base + 'DB_HOST']
    if os.environ.get(base + 'DB_PORT'):
        configmap['database']['port'] = int(os.environ[base + 'DB_PORT'])
    if os.environ.get(base + 'DB_USERNAME'):
        configmap['database']['username'] = os.environ[base + 'DB_USERNAME']
    if os.environ.get(base + 'DB_PASSWORD'):
        configmap['database']['password'] = os.environ[base + 'DB_PASSWORD']
    if os.environ.get(base + 'DB_NAME'):
        configmap['database']['dbname'] = os.environ[base + 'DB_NAME']
    if os.environ.get(base + 'METRICS_PORT'):
        configmap['metrics']['port'] = os.environ[base + 'METRICS_PORT']
    return configmap


def ensure_keys(configmap):
    """
    Ensure that the outer keys are present in the config map
    so we can safely insert the inner keys
    """
    if 'mqtt' not in configmap:
        configmap['mqtt'] = {}
    if 'database' not in configmap:
        configmap['database'] = {}
    if 'metrics' not in configmap:
        configmap['metrics'] = {}
    return configmap


def validate_configmap(configmap):
    pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    args = parser.parse_args()
    configmap = {}
    if args.config:
        try:
            with open(args.config, 'r') as stream:
                try:
                    configmap = yaml.load(stream)
                except yaml.YAMLError as e:
                    print("Unable to load configuration file: {0}".format(e))
        except IOError as e:
            print("Error loading configuration file: {0}".format(e))
    else:
        print("No configuration file specified")
    # Use environment variables to fill in anything missing from config file
    configmap = handle_environment_configuration(configmap)

    if 'port' not in configmap['metrics']:
        configmap['metrics']['port'] = 8000

    start_http_server(configmap['metrics']['port'])
    bridge = OwntracksToDatabaseBridge(configmap)
    bridge.run()
