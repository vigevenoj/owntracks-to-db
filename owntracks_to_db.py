#! /usr/bin/env python
"""
Store owntracks location updates in a database
"""
from datetime import datetime, timezone
import json
import paho.mqtt.client as mqtt
import psycopg2
import ssl
import sys
import yaml


class Dumper():
    def __init__(self, config='./.owntrackstodb.yaml'):
        try:
            with open(config, 'r') as f:
                configs = yaml.load(f.read())

                dbhost = configs['database']['host']
                dbport = configs['database']['port']
                dbuser = configs['database']['username']
                dbpass = configs['database']['password']
                dbname = configs['database']['dbname']

                self._conn = psycopg2.connect(host=dbhost, port=dbport,
                                              user=dbuser, password=dbpass,
                                              dbname=dbname)

                self._client = mqtt.Client(client_id="")
                try:
                    self._client.tls_set(ca_certs=configs['mqtt']['ca'],
                                         cert_reqs=ssl.CERT_REQUIRED,
                                         tls_version=ssl.PROTOCOL_TLSv1)
                except IOError as e:
                    print("Something went wrong while setting up mqtt. {0}"
                          .format(e))
                self._client.username_pw_set(configs['mqtt']['username'],
                                             configs['mqtt']['password'])
                self._client.will_set("/lwt/o2db",
                                      payload="o2db script offline")
                mqtt_host = configs['mqtt']['host']
                mqtt_port = configs['mqtt']['port']
                self._client.connect(mqtt_host, mqtt_port)
                # Don't subscribe until after we have the database set up
                # self._client.subscribe([("owntracks/#', 0)])
        except IOError as e:
            print("Unable to load configuration. {0}".format(e))
            sys.exit(1)

    def handle_location_update(self, user, device, rawdata):
        acc = rawdata['acc']  # accuracy in meters
        alt = rawdata['alt']  # altitude above sea level
        batt = rawdata['batt']  # battery percentage
        cog = rawdata['cog']  # course over ground
        lat = rawdata['lat']  # latitude
        lon = rawdata['lon']  # longitude
        rad = rawdata['rad']  # radius around region
        t = rawdata['t']  # p, c, b, r, u, t; see booklet
        tid = rawdata['tid']  # tracker ID
        tst = datetime.fromtimestamp(rawdata['tst'], timezone.utc)  # Timestamp
        vac = rawdata['vac']  # vertical accuracy
        vel = rawdata['vel']  # velocity, kmh
        pressure = rawdata['p']  # barometric pressure in kPa (float)
        connection_status = rawdata['conn']  # connection status: w, o, m

        # execute prepared statement
        cur = self._conn.cursor()
        cur.execute(
            """insert into locationupdates (acc, alt, batt, cog, lat, lon, radius, t, tid, tst, vac, vel, p, conn, rawdata)
            values (%(acc)s, %(alt)s, %(batt)s, %(cog)s, %(lat)s, %(lon)s, %(rad)s, %(t)s, %(tid)s, %(tst)s, %(vac)s, %(vel)s, %(p)s, %(conn)s, %(rawdata)s);""",
            {'acc': acc, 'alt': alt, 'batt': batt, 'cog': cog, 'lat': lat, 'lon': lon, 'rad': rad, 't': t, 'tid': tid, 'tst': tst, 'vac': vac, 'vel': vel, 'p': pressure, 'conn': connection_status, 'rawdata': rawdata})

    def handle_message(self):
        # Handle a sinle owntrakcs message
        # topic will be 'owntracks/user/device'
        # the message will be a json hash
        pass

    def run(self):
        self._client.subscribe([("owntracks/#", 0)])
        pass

if __name__ == '__main__':
    dumper = Dumper()
    # dumper._client.loop_forever()
    dumper.run()
