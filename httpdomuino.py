import argparse
import asyncio
import logging

import serialserver
import httpclient
import httpserver

DEFAULT_HTTP_PORT = 9090

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-S", "--server", nargs="*", help="Run Domuino server")
    parser.add_argument("-P", "--post", action="store_true", help="Send Domuino HTTP command")
    args = parser.parse_args()
    loop = asyncio.get_event_loop()

    if args.server is not None:
        asyncio.ensure_future(httpserver.main(loop, args.server[0] if len(args.server) else DEFAULT_HTTP_PORT))
        asyncio.ensure_future(serialserver.main(loop))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
    if args.post:
        loop.run_until_complete(httpclient.main("ARDUINO_TEST", "MEM", DEFAULT_HTTP_PORT))
    loop.close()
