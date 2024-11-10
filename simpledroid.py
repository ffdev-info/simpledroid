"""Convert Wikidata SPARQL results into a DROID compatible signature
file.
"""

import asyncio

from src.simpledroid import simpledroid


async def main():
    """Primary entry point for this script."""
    await simpledroid.main()


if __name__ == "__main__":
    asyncio.run(main())
