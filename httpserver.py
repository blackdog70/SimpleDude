import logging

from aiohttp import web

from protocol import prepare_commands, NET_CONFIG, get_device
from serialserver import protocol_out

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


async def handle_post(request):
    device_name = request.match_info.get('device', None)
    name = request.match_info.get('name', None)
    d = get_device(device_name)
    state = False
    if d.get('config'):
        if d['config'].get('LIGHT', 0):
            if request.has_body:
                packets = prepare_commands(device_name, {"LIGHT": name})
                await protocol_out(packets)
            state = {"state": any(map(lambda x, y: x and y, d['state'], d['lights'][name]))}
        elif d['config'].get('DHT', 0):
            packets = prepare_commands(device_name, "DHT")
            res = await protocol_out(packets)
            if len(res):
                state = {"temperature": res[0]["temperature"], "humidity": res[0]["humidity"]}
    LOGGER.info(f"{device_name}:{name} state is {state}")
    return web.json_response(state)


async def main(loop, port):
    app = web.Application()
    app.router.add_routes([web.post('/{device}/{name}', handle_post),
                           web.get('/{device}/{name}', handle_post)])
    runner = web.AppRunner(app)
    await runner.setup()
    srv = web.TCPSite(runner, '0.0.0.0', port)
    await srv.start()
    LOGGER.info('HTTP server started')
    LOGGER.info(f'serving on {srv.name}')
    return runner, srv

