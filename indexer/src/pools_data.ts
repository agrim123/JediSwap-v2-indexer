import {
    Block,
    EventWithTransaction,
  } from "../common/deps.ts";
  import {
    EVENTS,
    COLLECTION_NAMES,
    SELECTOR_KEYS,
    POOL_CONTRACT,
    INDEX_FROM_BLOCK,
    MONGODB_CONNECTION_STRING,
    DB_NAME,
    STREAM_URL,
  } from "../common/constants.ts";
  
  const filter = {
    header: { weak: true },
    events: [
      {
        fromAddress: POOL_CONTRACT,
        keys: [SELECTOR_KEYS.MINT],
        includeTransaction: false,
        includeReceipt: false,
      }, {
        fromAddress: POOL_CONTRACT,
        keys: [SELECTOR_KEYS.BURN],
        includeTransaction: false,
        includeReceipt: false,
      }, {
        fromAddress: POOL_CONTRACT,
        keys: [SELECTOR_KEYS.SWAP],
        includeTransaction: false,
        includeReceipt: false,
      }, {
        fromAddress: POOL_CONTRACT,
        keys: [SELECTOR_KEYS.COLLECT],
        includeTransaction: false,
        includeReceipt: false,
      },
    ],
  };
  
  export const config = {
    streamUrl: STREAM_URL,
    network: "starknet",
    filter,
    finality: "DATA_STATUS_ACCEPTED",
    startingBlock: INDEX_FROM_BLOCK,
    sinkType: "mongo",
    sinkOptions: {
      database: DB_NAME,
      connectionString: MONGODB_CONNECTION_STRING,
      collectionName: COLLECTION_NAMES.POOLS_DATA,
    },
  };
    
  export default function transform({ header, events }: Block) {
    const output = events.map(({ event }: EventWithTransaction) => {
      const key = event.keys[0];
      switch (key) {
        case SELECTOR_KEYS.MINT: {
          const poolAddress = event.fromAddress;
          const sender = event.data[0];
          const owner = event.data[1];
          const tickLower = event.data[2];
          const tickUpper = event.data[4];
          const amount = Number(event.data[6]);
          const amount0 = Number(event.data[7]);
          const amount1 = Number(event.data[9]);
          return {
            event: EVENTS.MINT,
            poolAddress,
            sender,
            owner,
            tickLower,
            tickUpper,
            amount,
            amount0,
            amount1,
            timestamp: header?.timestamp,
            block: Number(header?.blockNumber),
          };
        };
        case SELECTOR_KEYS.BURN: {
          const poolAddress = event.fromAddress;
          const owner = event.data[0];
          const tickLower = event.data[1];
          const tickUpper = event.data[3];
          const amount = Number(event.data[5]);
          const amount0 = Number(event.data[6]);
          const amount1 = Number(event.data[8]);
          return {
            event: EVENTS.BURN,
            poolAddress,
            owner,
            tickLower,
            tickUpper,
            amount,
            amount0,
            amount1,
            timestamp: header?.timestamp,
            block: Number(header?.blockNumber),
          };
        };
        case SELECTOR_KEYS.SWAP: {
          const poolAddress = event.fromAddress;
          const sender = event.data[0];
          const recipient = event.data[1];
          const amount0 = Number(event.data[2]);
          const amount1 = Number(event.data[5]);
          const sqrtPriceX96 = Number(event.data[8]);
          const liquidity = Number(event.data[10])
          const tick = event.data[11];
          return {
            event: EVENTS.SWAP,
            poolAddress,
            sender,
            recipient,
            amount0,
            amount1,
            sqrtPriceX96,
            liquidity,
            tick,
            timestamp: header?.timestamp,
            block: Number(header?.blockNumber),
          };
        };
        case SELECTOR_KEYS.COLLECT: {
          const poolAddress = event.fromAddress;
          const owner = event.data[0];
          const recipient = event.data[1];
          const tickLower = event.data[2];
          const tickUpper = event.data[4];
          const amount0 = Number(event.data[6]);
          const amount1 = Number(event.data[7]);
          return {
            event: EVENTS.COLLECT,
            poolAddress,
            owner,
            recipient,
            tickLower,
            tickUpper,
            amount0,
            amount1,
            timestamp: header?.timestamp,
            block: Number(header?.blockNumber),
          };
        };
        default:
          return;
      }
    }).filter(Boolean);;

    return output;
  }
  