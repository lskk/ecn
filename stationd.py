# ECN Station Daemon
# Processes telemetry data for all stations: ECN Stationary v1, ECN Stationary v2, ECN Mobile v2
import logging
import os
from datetime import datetime, timedelta
import json
import pika
from pika.amqp_object import Method
from pika.channel import Channel
from pika.frame import Method
import pymongo
from pymongo import MongoClient

MONGODB_URI = os.environ['MONGODB_URI']
AMQP_HOST = os.environ['AMQP_HOST']
AMQP_VHOST = os.environ['AMQP_VHOST']
AMQP_USER = os.environ['AMQP_USER']
AMQP_PASSWORD = os.environ['AMQP_PASSWORD']
PPTIK_GRAVITY = 9.77876
STATION_V1 = 'L'
STATION_STATIONARY = 'S'
STATION_MOBILE = 'M'

logging.basicConfig(level=logging.DEBUG)


class StationState:
    ALERT = 'A'
    READY = 'R'
    ECO = 'E'
    HIGH_RATE = 'H'
    NORMAL_RATE = 'N'
    LOST = 'L'


class StationaryV1Handler:
    logger = logging.getLogger(__name__)

    def __init__(self, db: pymongo.database.Database):
        self.db: pymongo.database.Database = db

    def receive(self, body: bytearray):
        body = body.replace(b'nan,', b'null,') # Workaround for ECNv1 bug
        # logger.debug('Decoding %s', body)
        msg = json.loads(body)
        client_id = msg['clientID']
        station_coll: pymongo.collection.Collection = db.station
        station = station_coll.find_one({'k': STATION_V1, 'i': client_id}, projection={'_id': 1})
        if not station:
            self.logger.error('Unknown v1 station: %s', client_id)
            return
        station_id = station['_id']
        # self.logger.debug('Station: %s', station_id)
        accel_coll: pymongo.collection.Collection = db.accel
        ts = datetime.utcnow() - timedelta(seconds=1)
        tstr = ts.strftime('%Y%m%d%H')
        accel_id = '%s:%s' % (tstr, station_id)
        self.logger.debug('Accel ID: %s at %s:%s', accel_id, ts.minute, ts.second)

        existing_accel_doc = accel_coll.find_one({'_id': accel_id}, projection={'_id': 1})
        if not existing_accel_doc:
            # Preallocate arrays except innermost
            accels = [[None for sec in range(60)] for min in range(60)]
            accel_coll.insert_one({'_id': accel_id, 'r': 40, 'z': accels, 'n': accels, 'e': accels})

        if client_id == 'ECN-4':
            z_values = [(orig['y'] + 6.598601 if orig['y'] else None) for orig in msg['accelerations']]
            n_values = [(orig['x'] if orig['x'] else None) for orig in msg['accelerations']]
            e_values = [(orig['z'] if orig['z'] else None) for orig in msg['accelerations']]
        else:
            z_values = [(-orig['z'] + PPTIK_GRAVITY if orig['z'] else None) for orig in msg['accelerations']]
            n_values = [(orig['x'] if orig['x'] else None) for orig in msg['accelerations']]
            e_values = [(orig['y'] if orig['y'] else None) for orig in msg['accelerations']]
        # Update accel Z/N/E
        # logger.debug('%s a.%d.%d Z = %s', accel_id, ts.minute, ts.second, z_values)
        accel_coll.update_one({'_id': accel_id}, {'$set': {
            'z.%d.%d' % (ts.minute, ts.second): z_values,
            'n.%d.%d' % (ts.minute, ts.second): n_values,
            'e.%d.%d' % (ts.minute, ts.second): e_values,
        }})
        # logger.debug('%s a.%d.%d Z = %s', accel_id, ts.minute, ts.second, z_values)
        # accel_z_coll.update_one({'_id': accel_id}, {'$set': {'a.%d.%d' % (ts.minute, ts.second): z_values}})
        # logger.debug('%s a.%d.%d NS = %s', accel_id, ts.minute, ts.second, n_values)
        # accel_n_coll.update_one({'_id': accel_id}, {'$set': {'a.%d.%d' % (ts.minute, ts.second): n_values}})
        # logger.debug('%s a.%d.%d EW = %s', accel_id, ts.minute, ts.second, e_values)
        # accel_e_coll.update_one({'_id': accel_id}, {'$set': {'a.%d.%d' % (ts.minute, ts.second): e_values}})

        # mark as 'H'igh rate
        station_coll.update_one({'_id': station_id}, {'$set': {'s': StationState.HIGH_RATE, 't': datetime.utcnow()}})


class AmqpProcessor:
    QUEUE_STATIONARY_V1 = 'ecn.stationary_v1'
    logger = logging.getLogger(__name__)

    def __init__(self):
        self.stationary_v1_handler = None

    def connect(self, host: str, vhost: str, username: str, password: str):
        logger.info('Connecting to RabbitMQ %s@%s:%s ...', username, host, vhost)
        params = pika.ConnectionParameters(host=host, virtual_host=vhost,
                                           credentials=pika.PlainCredentials(username, password))
        self.conn = pika.SelectConnection(parameters=params, on_open_callback=self.on_connected)

    def run(self):
        try:
            # Loop so we can communicate with RabbitMQ
            self.conn.ioloop.start()
        except KeyboardInterrupt:
            logger.info('Interrupted by keyboard, shutting down...')
            # Gracefully close the connection
            self.conn.close()
            # Loop until we're fully closed, will stop on its own
            self.conn.ioloop.start()

    def on_connected(self, connection: pika.BaseConnection):
        """Called when we are fully connected to RabbitMQ"""
        logger.info('Connected to RabbitMQ')
        connection.channel(self.on_channel_open)

    def on_channel_open(self, new_channel: Channel):
        """Called when our channel has opened"""
        self.channel = new_channel
        self.logger.info('Channel opened: %s', self.channel)
        self.channel.add_on_close_callback(
            lambda channel, reply_code, reply_text:
                self.logger.info('Channel closed: %s %s %s', channel.channel_number, reply_code, reply_text))
        self.logger.info('Consuming queue %s ...', self.QUEUE_STATIONARY_V1)
        consumer = self.channel.basic_consume(self.consume_stationary_v1, queue=self.QUEUE_STATIONARY_V1, no_ack=False,
                                   exclusive=True)
        self.logger.info('Consuming queue %s as %s', self.QUEUE_STATIONARY_V1, consumer)

    def consume_stationary_v1(self, channel: Channel, method, header, body):
        """Called when we receive a message from RabbitMQ"""
        self.stationary_v1_handler.receive(body)
        # self.logger.debug('Ack %s', method.delivery_tag)
        channel.basic_ack(method.delivery_tag)


logger = logging.getLogger(__name__)
logger.info('Connecting to MongoDB...')
mongo = MongoClient(MONGODB_URI)
db = mongo.ecn

processor = AmqpProcessor()
processor.stationary_v1_handler = StationaryV1Handler(db)
processor.connect(AMQP_HOST, AMQP_VHOST, AMQP_USER, AMQP_PASSWORD)
processor.run()