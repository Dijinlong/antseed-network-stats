# antseed-network-stats

Snapshot the whole [antseed](https://antseed.com) seller network into a single JSON blob.

## Why

If you sell capacity on antseed, the only way to know whether your price is
competitive is to see everyone else's. `antseed network browse` prints it, but the
output is per-peer and awkward to diff over time.

This tool flattens it into one record per seller:

    peerId, displayName, price(input/output), trustScore, volumeUsd,
    sessions, onChainPoolStakeAnts, lastSeen

so you can answer questions like:

- What does the cheapest seller charge for model X?
- Where does my trust score sit, and how much of it is identity vs history vs power?
- Who has volume but a trust score of 0? (it happens more than you would think)

## Usage

    python stats.py --top 500 --sort volume --out snapshot.json

## Status

Early. Working against the current `network browse --json` output shape.
