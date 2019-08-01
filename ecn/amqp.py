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
                                           credentials=pika.PlainCredentials(username, password),
                                           # https://stackoverflow.com/a/16155184/122441
                                           # https://pika.readthedocs.io/en/stable/examples/heartbeat_and_blocked_timeouts.html
                                           heartbeat=600, blocked_connection_timeout=300)
        self.conn = pika.SelectConnection(parameters=params, on_open_callback=self.on_connected)

    def connect_and_run_forever(self, host: str, vhost: str, username: str, password: str):
        while True:
            self.connect(host, vhost, username, password)
            try:
                # Loop so we can communicate with RabbitMQ
                self.conn.ioloop.start()
            except KeyboardInterrupt:
                self.logger.info('Interrupted by keyboard, shutting down...')
                # Gracefully close the connection
                self.conn.close()
                # Loop until we're fully closed, will stop on its own
                self.conn.ioloop.start()
                break

            # Gracefully close the connection
            self.conn.close()
            # Loop until we're fully closed, will stop on its own
            self.conn.ioloop.start()
            # Reconnect if not KeyboardInterrupt
            self.logger.info('Reconnecting...')
            time.sleep(1)

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
        connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, new_channel: Channel):
        """Called when our channel has opened"""
        self.channel = new_channel
        self.logger.info('Channel opened: %s', self.channel)
        self.channel.add_on_close_callback(
            lambda channel, reason:
                self.logger.info('Channel closed: %s %s', channel.channel_number, reason))
        # Subscribe stationary v1 queue
        if self.stationary_v1_handler:
            self.logger.info('Consuming queue %s ...', self.QUEUE_STATIONARY_V1)
            consumer = self.channel.basic_consume(queue=self.QUEUE_STATIONARY_V1, on_message_callback=self.consume_stationary_v1,
                                                    exclusive=True)
            self.logger.info('Consuming queue %s as %s', self.QUEUE_STATIONARY_V1, consumer)
        else:
            self.logger.warning('Not consuming queue %s: no handler', self.QUEUE_STATIONARY_V1)

        # Subscribe mobile stream queue
        if self.mobile_handler:
            self.logger.info('Consuming queue %s ...', self.QUEUE_MOBILE_STREAM)
            consumer = self.channel.basic_consume(queue=self.QUEUE_MOBILE_STREAM, on_message_callback=self.consume_mobile_stream,
                                                    exclusive=True)
            self.logger.info('Consuming queue %s as %s', self.QUEUE_MOBILE_STREAM, consumer)
        else:
            self.logger.warning('Not consuming queue %s: no handler', self.QUEUE_MOBILE_STREAM)

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
