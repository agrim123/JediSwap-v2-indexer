from decimal import Decimal

from bson import Decimal128
from pymongo import MongoClient, UpdateOne
from pymongo.database import Database

from server.const import Collection, FACTORY_ADDRESS, ZERO_DECIMAL128
from server.pricing import EthPrice
from server.query_utils import get_pool, get_tokens_from_pool, filter_by_the_latest_value
from server.utils import to_decimal, convert_bigint_field

from pymongo import MongoClient, UpdateOne


class Event:
    MINT = 'Mint'
    BURN = 'Burn'
    SWAP = 'Swap'
    COLLECT = 'Collect'


class EventTracker:
    mint_count = 0
    swap_count = 0
    burn_count = 0


def update_factory_record(db: Database, factory_totalValueLockedETH: Decimal, pool_totalValueLockedETH: Decimal):
        db[Collection.FACTORIES].update_one({'address': FACTORY_ADDRESS}, {
        '$set': {
            'totalValueLockedUSD': Decimal128((factory_totalValueLockedETH + pool_totalValueLockedETH) * EthPrice.get()),
            'totalValueLockedETH': Decimal128(factory_totalValueLockedETH + pool_totalValueLockedETH)
            },
        '$inc': {"txCount": 1},
    })


def yield_pool_data_records(db: Database) -> dict:
    # TODO: get records from a specific pool
    last_block_record = db[Collection.POOLS_DATA].find(
        {'processed': True}, { 'block': 1, '_id': 0}
        ).sort({'block': -1}).limit(1)
    try:
        last_block = next(last_block_record)['block']
    except StopIteration:
        last_block = 0

    records_query = {
        'block': { '$gt': last_block},
        '$or': [
            {'processed': {'$exists': False}},
            {'processed': False}
        ]}
    for record in db[Collection.POOLS_DATA].find(records_query).sort('timestamp', 1):
        yield record


def get_factory_record(db: Database) -> dict:
    return db[Collection.FACTORIES].find_one({'address': FACTORY_ADDRESS})


def handle_mint(db: Database, record: dict, factory: dict):
    pool = get_pool(db, record['poolAddress'])
    token0, token1 = get_tokens_from_pool(db, pool)
    amount0 = to_decimal(record['amount0'], token0['decimals'])
    amount1 = to_decimal(record['amount1'], token1['decimals'])

    token0_derivedETH = token0['derivedETH'].to_decimal()
    token1_derivedETH = token1['derivedETH'].to_decimal()

    pool_totalValueLockedETH = pool.get('totalValueLockedETH', ZERO_DECIMAL128).to_decimal()
    factory_totalValueLockedETH = factory['totalValueLockedETH'].to_decimal() - pool_totalValueLockedETH

    tokens_update_operations = [
        UpdateOne({"_id": token0['_id']}, {
            "$set": {"totalValueLockedUSD": Decimal128((token0['totalValueLocked'].to_decimal() + amount0) * token0_derivedETH * EthPrice.get())}, 
            "$inc": {"totalValueLocked": Decimal128(amount0)}}),
        UpdateOne({"_id": token1['_id']}, {
            "$set": {"totalValueLockedUSD": Decimal128((token1['totalValueLocked'].to_decimal() + amount1) * token1_derivedETH * EthPrice.get())}, 
            "$inc": {"totalValueLocked": Decimal128(amount1)}}),
    ]
    db[Collection.TOKENS].bulk_write(tokens_update_operations)

    pool_tick = pool.get('tick')
    if pool_tick:
        pool_tick = convert_bigint_field(pool_tick)

    pool_update_data = {'$inc': {}}
    if (pool_tick is not None and
            convert_bigint_field(record['tickLower']) <= pool_tick < convert_bigint_field(record['tickUpper'])):
        pool_update_data["$inc"]["liquidity"] = Decimal128(record['amount'])

    pool_totalValueLockedToken0 = pool.get('totalValueLockedToken0', ZERO_DECIMAL128).to_decimal()
    pool_totalValueLockedToken1 = pool.get('pool_totalValueLockedToken1', ZERO_DECIMAL128).to_decimal()
    pool_totalValueLockedETH = ((pool_totalValueLockedToken0 + amount0) * token0_derivedETH) + (
        (pool_totalValueLockedToken1 + amount1) * token1_derivedETH)
    
    pool_update_data["$inc"]['totalValueLockedToken0'] = Decimal128(amount0)
    pool_update_data["$inc"]['totalValueLockedToken1'] = Decimal128(amount1)
    pool_update_data["$set"] = {
        'totalValueLockedETH': Decimal128(pool_totalValueLockedETH),
        'totalValueLockedUSD': Decimal128(pool_totalValueLockedETH * EthPrice.get()),
    }

    pool_query = {"_id": pool['_id']}
    filter_by_the_latest_value(pool_query)
    db[Collection.POOLS].update_one(pool_query, pool_update_data)

    update_factory_record(db, factory_totalValueLockedETH, pool_totalValueLockedETH)
    EventTracker.mint_count += 1


def handle_burn(db: Database, record: dict, factory: dict):
    pool = get_pool(db, record['poolAddress'])
    token0, token1 = get_tokens_from_pool(db, pool)
    amount0 = to_decimal(record['amount0'], token0['decimals'])
    amount1 = to_decimal(record['amount1'], token1['decimals'])

    token0_derivedETH = token0['derivedETH'].to_decimal()
    token1_derivedETH = token1['derivedETH'].to_decimal()

    pool_totalValueLockedETH = pool.get('totalValueLockedETH', ZERO_DECIMAL128).to_decimal()
    factory_totalValueLockedETH = factory['totalValueLockedETH'].to_decimal() - pool_totalValueLockedETH

    tokens_update_operations = [
        UpdateOne({"_id": token0['_id']}, {
            "$set": {"totalValueLockedUSD": Decimal128((token0['totalValueLocked'].to_decimal() - amount0) * token0_derivedETH * EthPrice.get())}, 
            "$inc": {"totalValueLocked": Decimal128(-amount0)}}),
        UpdateOne({"_id": token1['_id']}, {
            "$set": {"totalValueLockedUSD": Decimal128((token1['totalValueLocked'].to_decimal() - amount1) * token1_derivedETH * EthPrice.get())}, 
            "$inc": {"totalValueLocked": Decimal128(-amount1)}}),
    ]
    db[Collection.TOKENS].bulk_write(tokens_update_operations)

    pool_tick = pool.get('tick')
    if pool_tick:
        pool_tick = convert_bigint_field(pool_tick)

    pool_update_data = {'$inc': {}}
    if (pool_tick is not None and
            convert_bigint_field(record['tickLower']) <= pool_tick < convert_bigint_field(record['tickUpper'])):
        pool_update_data["$inc"]["liquidity"] = Decimal128(-record['amount'])

    pool_totalValueLockedToken0 = pool.get('totalValueLockedToken0', ZERO_DECIMAL128).to_decimal()
    pool_totalValueLockedToken1 = pool.get('pool_totalValueLockedToken1', ZERO_DECIMAL128).to_decimal()
    pool_totalValueLockedETH = ((pool_totalValueLockedToken0 - amount0) * token0_derivedETH) + (
        (pool_totalValueLockedToken1 - amount1) * token1_derivedETH)
    
    pool_update_data["$inc"]['totalValueLockedToken0'] = Decimal128(-amount0)
    pool_update_data["$inc"]['totalValueLockedToken1'] = Decimal128(-amount1)
    pool_update_data["$set"] = {
        'totalValueLockedETH': Decimal128(pool_totalValueLockedETH),
        'totalValueLockedUSD': Decimal128(pool_totalValueLockedETH * EthPrice.get()),
    }

    pool_query = {"_id": pool['_id']}
    filter_by_the_latest_value(pool_query)
    db[Collection.POOLS].update_one(pool_query, pool_update_data)

    update_factory_record(db, factory_totalValueLockedETH, pool_totalValueLockedETH)
    EventTracker.burn_count += 1


def handle_swap(db: Database, record: dict, factory: dict):
    pool = get_pool(db, record['poolAddress'])
    token0, token1 = get_tokens_from_pool(db, pool)
    amount0 = to_decimal(record['amount0'], token0['decimals'])
    amount1 = to_decimal(record['amount1'], token1['decimals'])

    old_tick = pool.get('tick')
    if old_tick:
        old_tick = convert_bigint_field(old_tick)

    token0_derivedETH = token0['derivedETH'].to_decimal()
    token1_derivedETH = token1['derivedETH'].to_decimal()

    amount0_abs = abs(amount0)
    amount1_abs = abs(amount1)

    amount0_ETH = amount0_abs * token0_derivedETH
    amount1_ETH = amount1_abs * token1_derivedETH

    amount0_USD = amount0_ETH * EthPrice.get()
    amount1_USD = amount1_ETH * EthPrice.get()

    amount_total_USD_tracked = get_tracked_amount_usd(amount0_abs, token0['address'], token0_derivedETH, amount1_abs, token1['address'], token1_derivedETH) / 2 # TODO
    amount_total_ETH_tracked = amount_total_USD_tracked / EthPrice.get()

    amount_total_USD_untracked = (amount0_USD + amount1_USD) / 2

    fees_ETH = amount_total_ETH_tracked * pool['fee'] / 1000000
    fees_USD = amount_total_USD_untracked * pool['fee'] / 1000000

    factory_update_data = dict()
    factory_update_data['inc'] = dict()
    factory_update_data['set'] = dict()
    factory_update_data['inc']['txCount'] = 1
    factory_update_data['inc']['totalVolumeETH'] = amount_total_ETH_tracked
    factory_update_data['inc']['totalVolumeUSD'] = amount_total_USD_tracked
    factory_update_data['inc']['untrackedVolumeUSD'] = amount_total_USD_untracked
    factory_update_data['inc']['totalFeesETH'] = fees_ETH
    factory_update_data['inc']['totalFeesUSD'] = fees_USD

    pool_update_data = dict()
    pool_update_data['inc'] = dict()
    pool_update_data['set'] = dict()
    pool_update_data['inc']['volumeToken0'] = amount0_abs
    pool_update_data['inc']['volumeToken1'] = amount1_abs
    pool_update_data['inc']['volumeUSD'] = amount_total_USD_tracked
    pool_update_data['inc']['untrackedVolumeUSD'] = amount_total_USD_untracked
    pool_update_data['inc']['feesUSD'] = fees_USD
    pool_update_data['inc']['txCount'] = 1
    
    pool_update_data['set']['liquidity'] = record['liquidity']
    pool_update_data['set']['tick'] = record['tick']
    pool_update_data['set']['sqrt_price'] = record['sqrt_price_X96']
    pool_totalValueLockedToken0 = pool['totalValueLockedToken0'] + amount0
    pool_totalValueLockedToken1 = pool['totalValueLockedToken1'] + amount1
    pool_update_data['set']['totalValueLockedToken0'] = pool_totalValueLockedToken0
    pool_update_data['set']['totalValueLockedToken1'] = pool_totalValueLockedToken1

    token0_update_data = dict()
    token0_update_data['inc'] = dict()
    token0_update_data['set'] = dict()
    token0_update_data['inc']['volume'] = amount0_abs
    token0_totalValueLocked = token0['totalValueLocked'] + amount0
    token0_update_data['inc']['volumeUSD'] = amount_total_USD_tracked
    token0_update_data['inc']['untrackedVolumeUSD'] = amount_total_USD_untracked
    token0_update_data['inc']['feesUSD'] = fees_USD
    token0_update_data['inc']['txCount'] = 1

    token1_update_data = dict()
    token1_update_data['inc'] = dict()
    token1_update_data['set'] = dict()
    token1_update_data['inc']['volume'] = amount1_abs
    token1_totalValueLocked = token1['totalValueLocked'] + amount1
    token1_update_data['inc']['volumeUSD'] = amount_total_USD_tracked
    token1_update_data['inc']['untrackedVolumeUSD'] = amount_total_USD_untracked
    token1_update_data['inc']['feesUSD'] = fees_USD
    token1_update_data['inc']['txCount'] = 1

    prices = sqrt_price_X96_to_token_prices(record['sqrt_price_X96'], token0['decimals'], token1['decimals']) # TODO
    pool_update_data['set']['token0Price'] = prices[0]
    pool_update_data['set']['token1Price'] = prices[1]

    # TODO update_eth_price

    token0_derivedETH = token0_update_data['set']['derivedETH'] = find_eth_per_token(token0) # TODO
    token1_derivedETH = token1_update_data['set']['derivedETH'] = find_eth_per_token(token1) # TODO
    
    factory_totalValueLockedETH = factory['totalValueLockedETH'].to_decimal() - pool.get('totalValueLockedETH', ZERO_DECIMAL128).to_decimal()

    pool_totalValueLockedETH = (pool_totalValueLockedToken0 * token0_derivedETH) + (pool_totalValueLockedToken1 * token1_derivedETH)
    pool_update_data['set']['totalValueLockedETH'] = pool_totalValueLockedETH
    pool_update_data['set']['totalValueLockedUSD'] = pool_totalValueLockedETH * EthPrice.get()

    factory_totalValueLockedETH = factory_totalValueLockedETH + pool_totalValueLockedETH
    factory_update_data['set']['totalValueLockedETH'] = factory_totalValueLockedETH
    factory_update_data['set']['totalValueLockedUSD'] = factory_totalValueLockedETH * EthPrice.get()

    token1_update_data['set']['totalValueLocked'] = token0_totalValueLocked
    token1_update_data['set']['totalValueLockedUSD'] = token0_totalValueLocked * token0_derivedETH * EthPrice.get()

    token1_update_data['set']['totalValueLocked'] = token1_totalValueLocked
    token1_update_data['set']['totalValueLockedUSD'] = token1_totalValueLocked * token1_derivedETH * EthPrice.get()

    # TODO
    # write_factory_update_data()
    # write_pool_update_data()
    # write_token0_update_data()
    # write_token1_update_data()
    
    EventTracker.swap_count += 1


EVENT_TO_FUNCTION_MAP = {
    Event.MINT: handle_mint,
    # Event.SWAP: handle_swap, # TODO
    Event.BURN: handle_burn,
}


def run(mongo_url: str, mongo_database: Database, rpc_url: str):
    processed_records = []
    EthPrice.set(rpc_url)
    with MongoClient(mongo_url) as mongo:
        db_name = mongo_database.replace('-', '_')
        db = mongo[db_name]
        for record in yield_pool_data_records(db):
            event_func = EVENT_TO_FUNCTION_MAP.get(record['event'])
            if event_func:
                factory = get_factory_record(db)
                event_func(db, record, factory)
                processed_records.append(
                    UpdateOne({"_id": record['_id']}, {"$set": {"processed": True}})
                )
        if processed_records:
            db[Collection.POOLS_DATA].bulk_write(processed_records)

    print(f'Successfully processed {EventTracker.mint_count} Mint events')
    print(f'Successfully processed {EventTracker.burn_count} Burn events')
