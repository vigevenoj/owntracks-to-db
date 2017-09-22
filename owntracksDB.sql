-- create table for location updates
create table locationupdates(
  acc integer,
  alt integer,
  batt integer,
  cog integer,
  lat float,
  lon float,
  radius integer,
  t char(1),
  tid varchar(16),
  tst timestamp primary key,
  vac integer,
  vel integer,
  p integer,
  conn char(1),
  rawdata json,
  userid varchar(64),
  device varchar(64)
);

create table users (
  userid int primary key, 
  username varchar(256), 
  password varchar(256), 
  email varchar(256), 
  join_date timestamp without time zone, 
  active boolean, 
  admin boolean
);

create table roles (
  id int primary key,
  name varchar(128),
  description varchar(256)
);
