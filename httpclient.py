import logging

import aiohttp
import async_timeout

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


async def fetch(session, url, payload):
    async with async_timeout.timeout(10):
        async with session.post(url, json=payload) as response:
            return await response.text()


async def main(value, port):
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, f'http://127.0.0.1:{port}/pippo', value)
        LOGGER.info(html)

