#!/opt/rh/ruby193/root/usr/bin/ruby
# -*- encoding: utf-8 -*-
#
# libraries
#   $ gem install mqtt
#   $ gem install pg
#   $ gem install logger
#

require 'bigdecimal'
require 'date'
require 'json'
require 'logger'
require 'mqtt'
require 'pg'
require 'rubygems'
require 'yaml'

class OwntracksUpdate
  # A struct to hold and validate an incoming message is a location update
  # before it is persisted to the database
  Version = '0.0.1'
  def initialize
  end
end


class OwntracksToDatabaseBridge
  # Subscribes to a mqtt broker for updates on the 'owntracks' channel,
  # validates the messages are location updates, and persists them to
  # a database
  Version = '0.0.1'

  def initialize(arguments, stdin)
    configuration = YAML::load_file(File.join(File.dirname(__FILE__), '.owntrackstodb.yaml'))
    @mqtt = MQTT::Client.new
    @mqtt.host = configuration['mqtt']['host'] 
    @mqtt.port = configuration['mqtt']['port']
    @mqtt.ssl = configuration['mqtt']['ssl']
    @mqtt.ca_file = configuration['mqtt']['ca_cert']
    @mqtt.username = configuration['mqtt']['username']
    @mqtt.password = configuration['mqtt']['password']

    # set up database configuration from yaml 
    # and connect to database
    dbhost = configuration['database']['host']
    dbport = configuration['database']['port']
    dbuser = configuration['database']['username']
    dbpass = configuration['database']['password']
    dbname = configuration['database']['dbname']
    @conn = PG.connect(:host => dbhost, :port => dbport, :user => dbuser, :password => dbpass, :dbname => dbname)
    @conn.prepare('locationupdate1', 'insert into locationupdates (acc, alt, batt, cog, lat, lon, radius, t, tid, tst, vac, vel, p, conn, rawdata, userid, device) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)')

    STDOUT.sync = true
    #@log = Logger.new(STDOUT)
    @log = Logger.new('owntrackstodb.log', 10, 1048576)
    @log.level = Logger::INFO

  end

  def handle_location_update(user, device, json)
    acc = json['acc'] # accuracy
    alt = json['alt'] # altitude
    batt = json['batt'] # battery percentage
    cog = json['cog'] # course over ground
    lat = json['lat'] # latitude
    lon = json['lon'] # longitude
    rad = json['rad'] # radius around region
    t  = json['t'] # p, c, b, r, u, t; see booklet
    tid = json['tid'] # tracker ID
    tst = Time.at(json['tst']).to_datetime # timestamp in epoch format
    vac = json['vac'] # vertical accuracy
    vel = json['vel'] # velocity, kmh
    pressure = json['p'] # barometric pressure in kPa (float)
    connection_status= json['conn'] # connection status: w, o, m; see booklet
    rawdata = json
    @log.info("rawdata is #{json}")

    # now that we have all the elements we need, we should insert them into the database
    @conn.exec_prepared('locationupdate1', [acc, alt, batt, cog, lat, lon, rad, t, tid, tst, vac, vel, pressure, connection_status, rawdata, user, device])

  end

  def handle_message(topic, message)
    @log.info("received mqtt message : topic=#{topic}, message=#{message}")
    # Handle a single owntracks message
    # topic will be 'owntracks/user/device'
    # the message will be a json hash
    user, device = topic.split("/")[1], topic.split("/")[2]
    json = JSON.parse(message)
    @log.info("#{user} #{device} posted an update: #{json}")
    # example message
    #  {"tst"=>1493917547, "acc"=>65, "_type"=>"location", "alt"=>19, "lon"=>-122.6809371528689, "vac"=>21, "p"=>101.0912551879883, "lat"=>45.52250024956788, "batt"=>52, "conn"=>"m", "tid"=>"jv"}
    if (json['_type'] == 'location')
      handle_location_update(user, device, json)
    end
  end

  def run
    begin
      @mqtt.connect() do |c|
        @log.info("Connection start...")
        c.get('owntracks/#') do |topic, message|
          handle_message topic, message
        end 
      end # end of connection
    rescue Exception => e
      @log.error(e)
    end
  end #end of run block
end #end class def

app = OwntracksToDatabaseBridge.new(ARGV, STDIN)
app.run
