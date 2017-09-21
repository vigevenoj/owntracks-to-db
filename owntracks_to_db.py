#! /usr/bin/env python
"""
Store owntracks location updates in a database
"""
from datetime import datetime, timezone
from prometheus_client import start_http_server, Counter, Gauge
import json
import logging
import logging.handlers
import paho.mqtt.client as mqtt
import psycopg2
import ssl
import sys
import time
import yaml


class OwntracksToDatabaseBridge():
    def __init__(self, config='./.owntrackstodb.yaml'):
        try:
            with open(config, 'r') as f:
                self.total_recieved_updates = Counter(
                    'total_received_updates',
                    'The number of updates received from the mqtt broker')
                self.total_persisted_updates = Counter(
                    'total_persisted_updates',
                    'The number of updates saved into the database')
                configs = yaml.load(f.read())
                self._last_persisted_timestamp = 0
                self._last_received_timestamp = 0
                self.persistance_lag = Gauge(
                    'persistence_lag',
                    'Seconds between most-recently-received update and ' +
                    'the most-recently-persisted update')

                logging.basicConfig(level=logging.INFO)
                self._logger = logging.getLogger(__name__)
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler = logging.handlers.RotatingFileHandler('o2db.log',
                                                               maxBytes=1048576,
                                                               backupCount=5)
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)

                dbhost = configs['database']['host']
                dbport = configs['database']['port']
                dbuser = configs['database']['username']
                dbpass = configs['database']['password']
                dbname = configs['database']['dbname']

                self._conn = psycopg2.connect(host=dbhost, port=dbport,
                                              user=dbuser, password=dbpass,
                                              dbname=dbname)

                # Handle mqtt messages from the channels we subscribe to
                def handle_message(client, userdata, message):
                    j = json.loads(str(message.payload, encoding="ascii"))
                    if(message.topic.startswith("owntracks")):
                        # If message format is 'owntracks/user/device'
                        # then we should try to parse out userid/deviceid
                        # and handle this message as a location update
                        if(j['_type'] == 'location'):
                            userid = message.topic.split('/')[1]
                            device = message.topic.split('/')[2]
                            self._logger.info("{0} {1} posted an update: {2}"
                                              .format(userid, device, j))
                            self.total_recieved_updates.inc()
                            self.handle_location_update(userid, device, j)

                self._client = mqtt.Client(client_id="")
                try:
                    self._client.tls_set(ca_certs=configs['mqtt']['ca'],
                                         cert_reqs=ssl.CERT_REQUIRED,
                                         tls_version=ssl.PROTOCOL_TLSv1)
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
                self._logger.warn("Connecting to mqtt broker...")
                self._client.connect(mqtt_host, mqtt_port)
        except IOError as e:
            self._logger.error("Unable to load configuration. {0}".format(e))
            sys.exit(1)

    def handle_location_update(self, user, device, rawdata):
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
        except Exception as e:
            # TODO We should try to persist this update again
            self._logger.error("Unable to execute query: {0}".format(e))

    def run(self):
        self._client.subscribe([("owntracks/#", 0)])
        self._logger.warn("subscribed to 'owntracks/#'")
        self._client.loop_forever()
        try:
            while True:
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            self._client.disconnect()

if __name__ == '__main__':
    start_http_server(8000)
    bridge = OwntracksToDatabaseBridge()
    bridge.run()
