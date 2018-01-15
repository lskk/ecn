# ECN Station Daemon
# Processes telemetry data for all stations: ECN Stationary v1, ECN Stationary v2, ECN Mobile v2
import logging
import os
from pymongo import MongoClient

from ecn.amqp import AmqpProcessor
from ecn.mobile import MobileHandler
from ecn.stationary_v1 import StationaryV1Handler

MONGODB_URI = os.environ['MONGODB_URI']
AMQP_HOST = os.environ['AMQP_HOST']
AMQP_VHOST = os.environ['AMQP_VHOST']
AMQP_USER = os.environ['AMQP_USER']
AMQP_PASSWORD = os.environ['AMQP_PASSWORD']

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.info('Connecting to MongoDB...')
mongo = MongoClient(MONGODB_URI)
db = mongo.ecn

processor = AmqpProcessor()
processor.stationary_v1_handler = StationaryV1Handler(db)
processor.mobile_handler = MobileHandler(db)
processor.connect(AMQP_HOST, AMQP_VHOST, AMQP_USER, AMQP_PASSWORD)
processor.run()