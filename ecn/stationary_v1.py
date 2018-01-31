import json
import logging
from datetime import datetime, timedelta

import pymongo

from ecn import StationKind, PPTIK_GRAVITY, StationState


class StationaryV1Handler:
    logger = logging.getLogger(__name__)
    SAMPLE_RATE = 40

    def __init__(self, db: pymongo.database.Database):
        self.db: pymongo.database.Database = db

    def receive(self, body: bytearray):
        body = body.replace(b'nan,', b'null,') # Workaround for ECNv1 bug
        # logger.debug('Decoding %s', body)
        try:
            msg = json.loads(body)
        except Exception as e:
            self.logger.error('Ignoring broken JSON: %s', str(body), exc_info = e)
            return
        client_id = msg['clientID']
        station_coll: pymongo.collection.Collection = self.db.station
        station = station_coll.find_one({'k': StationKind.V1, 'i': client_id}, projection={'_id': 1})
        if not station:
            self.logger.error('Unknown v1 station: %s', client_id)
            return
        station_id = station['_id']
        # self.logger.debug('Station: %s', station_id)
        accel_coll: pymongo.collection.Collection = self.db.accel
        ts = datetime.utcnow() - timedelta(seconds=1)
        tstr = ts.strftime('%Y%m%d%H')
        accel_id = '%s:%s' % (tstr, station_id)
        second_of_hour = (60 * ts.minute) + ts.second
        self.logger.debug('Accel ID: %s at %d (%d:%d)', accel_id, second_of_hour, ts.minute, ts.second)

        existing_accel_doc = accel_coll.find_one({'_id': accel_id}, projection={'_id': 1})
        if not existing_accel_doc:
            # "Preallocate" arrays except innermost
            accels = [None for sec in range(60 * 60)]
            self.logger.debug('Inserting stationary_v1 accel %s sample_rate=%d', accel_id, self.SAMPLE_RATE)
            accel_coll.insert_one({'_id': accel_id, 'r': self.SAMPLE_RATE, 'z': accels, 'n': accels, 'e': accels})

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
            'z.%d' % (second_of_hour): z_values,
            'n.%d' % (second_of_hour): n_values,
            'e.%d' % (second_of_hour): e_values,
        }})
        # logger.debug('%s a.%d.%d Z = %s', accel_id, ts.minute, ts.second, z_values)
        # accel_z_coll.update_one({'_id': accel_id}, {'$set': {'a.%d.%d' % (ts.minute, ts.second): z_values}})
        # logger.debug('%s a.%d.%d NS = %s', accel_id, ts.minute, ts.second, n_values)
        # accel_n_coll.update_one({'_id': accel_id}, {'$set': {'a.%d.%d' % (ts.minute, ts.second): n_values}})
        # logger.debug('%s a.%d.%d EW = %s', accel_id, ts.minute, ts.second, e_values)
        # accel_e_coll.update_one({'_id': accel_id}, {'$set': {'a.%d.%d' % (ts.minute, ts.second): e_values}})

        # mark as 'H'igh rate
        station_coll.update_one({'_id': station_id}, {'$set': {'s': StationState.HIGH_RATE, 't': datetime.utcnow()}})