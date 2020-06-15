import datetime
import asyncio
import serial_asyncio
import logging

from protocol import (MAX_PACKET_SIZE, PACKET_HEADER, PACKET_TIMEOUT, SEND_RETRY, QUERIES, PORTS, NET_CONFIG,
                      NET_ID, NET_REVERSEID,
                      Packet, parse_packet, execute)

SIZE = MAX_PACKET_SIZE - len(PACKET_HEADER)

queue_out = dict()
queue_in = dict()
reply = dict()
context = dict()

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


def log(log_msg, packet):
    value = {'type': log_msg,
             'time': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
             'node': packet.dest,
             'msg': QUERIES[packet.data[0]],
             'data': packet.data[1:]
             }
    LOGGER.info(value)


async def recv(r, com):
    while True:
        await r.readuntil(PACKET_HEADER)
        packet = Packet().deserialize(await r.read(SIZE))
        if packet is not None:
            c_key = f'{packet.source:02}{packet.dest:02}'
            if context.get(c_key, None):
                reply[com].put_nowait(packet[:SIZE])
                del context[c_key]
            else:
                queue_in[com].put_nowait(packet[:SIZE])


async def protocol_in(port, com):
    while True:
        received = await queue_in[com].get()
        result = parse_packet(received)
        packet = Packet(result['reply'], dest=received.source)
        port.write(packet.serialize())
        log("HUB[REPLY]->", packet)
        send(execute(result))


async def protocol_out(port, com):
    while True:
        if not queue_in[com].qsize():
            msg = await queue_out[com].get()
            context[f'{msg.dest:02}{msg.source:02}'] = msg
            for retry in range(SEND_RETRY):
                log(f"HUB[+{retry}]->", msg)
                port.write(msg.serialize())
                try:
                    msg = await asyncio.wait_for(reply[com].get(), timeout=PACKET_TIMEOUT)
                    log("->HUB", msg)
                    # todo: cosa ne faccio del messaggio di risposta?
                    break
                except asyncio.TimeoutError:
                    await asyncio.sleep(1)
            else:
                log("HUB->TIMEOUT", msg)


def send(msgs):
    for com, values in NET_CONFIG.items():
        for msg in msgs:
            if values.get(NET_REVERSEID[msg.dest], None):
                queue_out[com].put_nowait(msg)


async def main(loop):
    task = list()
    for com in PORTS:
        queue_out[com] = asyncio.Queue()
        queue_in[com] = asyncio.Queue()
        reply[com] = asyncio.Queue()

        reader, writer = await serial_asyncio.open_serial_connection(url=com, baudrate=19200)
        task.append(asyncio.create_task(recv(reader, com)))
        task.append(asyncio.create_task(protocol_in(writer, com)))
        task.append(asyncio.create_task(protocol_out(writer, com)))
        LOGGER.info(f'Reader/Writer created on port {com}')
    LOGGER.info('Serial server started')
    return task


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    loop.close()
