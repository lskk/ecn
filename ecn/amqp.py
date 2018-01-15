import logging

import os
import pika
from pika.channel import Channel


class AmqpProcessor:
    logger = logging.getLogger(__name__)

    QUEUE_STATIONARY_V1 = os.getenv('QUEUE_PREFIX', 'ecn_') + 'stationary_v1'
    '''QUEUE_PREFIX can be used for development, e.g. 'ecn_dev_'.'''
    QUEUE_MOBILE_STREAM = os.getenv('QUEUE_PREFIX', 'ecn_') + 'mobile_stream'
    '''QUEUE_PREFIX can be used for development, e.g. 'ecn_dev_'.'''

    def __init__(self):
        self.stationary_v1_handler = None
        self.mobile_handler = None

    def connect(self, host: str, vhost: str, username: str, password: str):
        self.logger.info('Connecting to RabbitMQ %s@%s:%s ...', username, host, vhost)
        params = pika.ConnectionParameters(host=host, virtual_host=vhost,
                                           credentials=pika.PlainCredentials(username, password))
        self.conn = pika.SelectConnection(parameters=params, on_open_callback=self.on_connected)

    def run(self):
        try:
            # Loop so we can communicate with RabbitMQ
            self.conn.ioloop.start()
        except KeyboardInterrupt:
            self.logger.info('Interrupted by keyboard, shutting down...')
            # Gracefully close the connection
            self.conn.close()
            # Loop until we're fully closed, will stop on its own
            self.conn.ioloop.start()

    def on_connected(self, connection: pika.BaseConnection):
        """Called when we are fully connected to RabbitMQ"""
        self.logger.info('Connected to RabbitMQ')
        connection.channel(self.on_channel_open)

    def on_channel_open(self, new_channel: Channel):
        """Called when our channel has opened"""
        self.channel = new_channel
        self.logger.info('Channel opened: %s', self.channel)
        self.channel.add_on_close_callback(
            lambda channel, reply_code, reply_text:
                self.logger.info('Channel closed: %s %s %s', channel.channel_number, reply_code, reply_text))
        # Subscribe stationary v1 queue
        self.logger.info('Consuming queue %s ...', self.QUEUE_STATIONARY_V1)
        consumer = self.channel.basic_consume(self.consume_stationary_v1, queue=self.QUEUE_STATIONARY_V1, no_ack=False,
                                   exclusive=True)
        self.logger.info('Consuming queue %s as %s', self.QUEUE_STATIONARY_V1, consumer)
        # Subscribe mobile stream queue
        self.logger.info('Consuming queue %s ...', self.QUEUE_MOBILE_STREAM)
        consumer = self.channel.basic_consume(self.consume_mobile_stream, queue=self.QUEUE_MOBILE_STREAM, no_ack=False,
                                   exclusive=True)
        self.logger.info('Consuming queue %s as %s', self.QUEUE_MOBILE_STREAM, consumer)

    def consume_stationary_v1(self, channel: Channel, method, header, body):
        """Called when we receive a message from RabbitMQ"""
        self.stationary_v1_handler.receive(body)
        # self.logger.debug('Ack %s', method.delivery_tag)
        channel.basic_ack(method.delivery_tag)

    def consume_mobile_stream(self, channel: Channel, method, header, body):
        """Called when we receive a message from RabbitMQ"""
        self.mobile_handler.receive(body)
        # self.logger.debug('Ack %s', method.delivery_tag)
        channel.basic_ack(method.delivery_tag)
