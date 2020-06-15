import logging

from aiohttp import web

from protocol import prepare_commands
from serialserver import send

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


async def handle_post(request):
    if request.has_body:
        name = request.match_info.get('name', None)
        commands = await request.json()
        packets = prepare_commands(name, commands)
        send(packets)
    return web.json_response({'reply': 'OK'})


async def handle(request):
    if request.has_body:
        name = await request.json()
        packets = prepare_commands(name)
        send(packets)
    return web.json_response({'reply': 'OK'})


async def main(loop, port):
    app = web.Application()
    app.router.add_routes([web.post('/switch', handle),
                           web.post('/switch/{name}', handle_post),
                           web.get('/switch/{name}', handle_post)])
    runner = web.AppRunner(app)
    await runner.setup()
    srv = web.TCPSite(runner, '0.0.0.0', port)
    await srv.start()
    LOGGER.info('HTTP server started')
    LOGGER.info(f'serving on {srv.name}')
    return runner, srv

