import datetime
import asyncio
import serial_asyncio
import logging

from protocol import (MAX_PACKET_SIZE, PACKET_HEADER, PACKET_TIMEOUT, SEND_RETRY, QUERIES, NET_CONFIG,
                      NET_REVERSEID, Packet, parse_packet, execute)

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
             'msg': QUERIES[packet.data[0]],
             'data': packet.data[1:]
             }
    LOGGER.info(value)


async def recv(com):
    while True:
        await NET_CONFIG[com]['reader'].readuntil(PACKET_HEADER)
        packet = Packet(bus=com).deserialize(await NET_CONFIG[com]['reader'].read(SIZE))
        if packet is not None:
            c_key = f'{packet.source:02}{packet.dest:02}'
            if context.get(c_key, None):
                # TODO: Valutare se si può evitare il dizionario e usare il bus del pacchetto
                reply[com].put_nowait(packet)
                del context[c_key]
            else:
                queue_in[com].put_nowait(packet)


async def protocol_in(com):
    while True:
        received = await queue_in[com].get()
        result = parse_packet(received)
        packet = Packet(result['reply'], dest=received.source)
        NET_CONFIG[com]['writer'].write(packet.serialize())
        log(f"{packet.source}[REPLY]->{packet.dest}", packet)
        await protocol_out(execute(result))


async def protocol_out(msgs):
    result = list()
    for com, values in NET_CONFIG.items():
        for msg in msgs:
            if values.get(NET_REVERSEID[msg.dest], None):
                context[f'{msg.dest:02}{msg.source:02}'] = msg
                for retry in range(SEND_RETRY):
                    log(f"{msg.source}[+{retry}]->{msg.dest}", msg)
                    NET_CONFIG[com]['writer'].write(msg.serialize())
                    try:
                        res = await asyncio.wait_for(reply[com].get(), timeout=PACKET_TIMEOUT)
                        log(f"{res.source}->{res.dest}", res)
                        result.append(parse_packet(res))
                        break
                    except asyncio.TimeoutError:
                        await asyncio.sleep(1)
                    except Exception as e:
                        LOGGER.error(f"OUT: {e}")
                else:
                    log(f"{msg.source}->TIMEOUT", msg)
    return result


# def send(msgs: list[Packet]) -> list[Packet]:
#     results = list()
#     for com, values in NET_CONFIG.items():
#         for msg in msgs:
#             if values.get(NET_REVERSEID[msg.dest], None):
#                 results.append(await protocol_out(com, msg))
#     return results


async def main(loop):
    task = list()
    for com in NET_CONFIG.keys():
        queue_out[com] = asyncio.Queue()
        queue_in[com] = asyncio.Queue()
        reply[com] = asyncio.Queue()
        LOGGER.info(f"Opening port {com}")
        reader, writer = await serial_asyncio.open_serial_connection(url=com, baudrate=38400)

        NET_CONFIG[com]['reader'] = reader
        NET_CONFIG[com]['writer'] = writer

        task.append(asyncio.create_task(recv(com)))
        task.append(asyncio.create_task(protocol_in(com)))
        LOGGER.info(f'Reader/Writer created on port {com}')
    LOGGER.info('Serial server started')
    return task


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
    loop.close()
