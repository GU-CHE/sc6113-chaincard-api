CREATE TABLE IF NOT EXISTS transactions (
    chain_id       INTEGER NOT NULL,
    tx_hash        CHAR(66) NOT NULL,
    from_address   CHAR(42) NOT NULL,
    to_address     CHAR(42),
    value_wei      NUMERIC(78, 0) NOT NULL,
    block_number   BIGINT,
    block_time     TIMESTAMPTZ,
    status         TEXT NOT NULL CHECK (status IN ('pending', 'success', 'failed')),
    saved_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chain_id, tx_hash)
);

CREATE INDEX IF NOT EXISTS transactions_saved_at_idx
    ON transactions (saved_at DESC);
