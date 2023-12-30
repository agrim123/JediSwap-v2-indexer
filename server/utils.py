from decimal import Decimal

from pymongo.database import Database

from const import Collection


def to_decimal(amount: int, decimals: int) -> Decimal:
    num = Decimal(10) ** Decimal(decimals)
    return Decimal(amount) / num


def convert_bigint_field(value: str) -> int:
    return int(value, 16)


def filter_by_the_latest_value(query: dict):
    query['_cursor.to'] = None


def get_pool(db: Database, pool_address: str) -> dict:
    # consider adding a cache mechanism
    pools_collection = db[Collection.POOLS]
    query = {'poolAddress': pool_address}
    filter_by_the_latest_value(query)
    return pools_collection.find_one(query)


def get_tokens_from_pool(db: Database, existing_pool: dict) -> tuple[dict, dict]:
    # consider adding a cache mechanism
    token0_address = existing_pool['token0']
    token1_address = existing_pool['token1']

    tokens_collection = db[Collection.TOKENS]
    token0 = tokens_collection.find_one({'address': token0_address})
    token1 = tokens_collection.find_one({'address': token1_address})
    return token0, token1
