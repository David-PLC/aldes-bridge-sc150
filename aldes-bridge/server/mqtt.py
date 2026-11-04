"""Codec MQTT 3.1.1 nativo."""
import struct

PT_CONNECT = 1
PT_CONNACK = 2
PT_PUBLISH = 3
PT_PUBACK = 4
PT_PUBREC = 5
PT_PUBREL = 6
PT_PUBCOMP = 7
PT_SUBSCRIBE = 8
PT_SUBACK = 9
PT_PINGREQ = 12
PT_PINGRESP = 13
PT_DISCONNECT = 14


class MQTTError(Exception):
    pass


def encode_remaining_length(n):
    out = bytearray()
    while True:
        b = n % 128
        n //= 128
        if n > 0:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


class MQTTReader:
    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise MQTTError("EOF")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def read_packet(self):
        try:
            h = self._read(1)
        except MQTTError:
            return None
        ptype = (h[0] >> 4) & 0xF
        flags = h[0] & 0xF
        rl_bytes = b""
        mult, shift, rl = 1, 0, 0
        while True:
            b = self._read(1)[0]
            rl_bytes += bytes([b])
            rl += (b & 0x7F) * mult
            if not (b & 0x80):
                break
            mult *= 128
            shift += 7
            if shift > 28:
                raise MQTTError("remaining length troppo lungo")
        body = self._read(rl) if rl else b""
        return ptype, flags, body, h + rl_bytes + body


def parse_string(buf, o):
    if o + 2 > len(buf):
        raise MQTTError("frame corto")
    n = struct.unpack_from(">H", buf, o)[0]
    o += 2
    if o + n > len(buf):
        raise MQTTError("stringa fuori limite")
    return buf[o:o + n].decode("utf-8", errors="replace"), o + n


def parse_connect(payload):
    o = 0
    proto, o = parse_string(payload, o)
    level = payload[o]; o += 1
    cflags = payload[o]; o += 1
    keepalive = struct.unpack_from(">H", payload, o)[0]; o += 2
    client_id, o = parse_string(payload, o)
    return {"proto": proto, "level": level, "cflags": cflags, "keepalive": keepalive, "client_id": client_id}


def parse_publish_full(body, flags):
    topic, o = parse_string(body, 0)
    qos = (flags >> 1) & 0x3
    if qos:
        if o + 2 > len(body):
            raise MQTTError("PUBLISH QoS senza pkt_id")
        pkt_id = struct.unpack_from(">H", body, o)[0]
        o += 2
    else:
        pkt_id = None
    return topic, qos, pkt_id, body[o:]


def parse_subscribe(payload):
    pkt_id = struct.unpack_from(">H", payload, 0)[0]
    o = 2
    topics = []
    while o < len(payload):
        t, o = parse_string(payload, o)
        qos = payload[o]; o += 1
        topics.append((t, qos))
    return pkt_id, topics


def build_connack(rc=0):
    return b"\x20\x02\x00" + bytes([rc])


def build_puback(pkt_id):
    return b"\x40\x02" + struct.pack(">H", pkt_id)


def build_pubrec(pkt_id):
    return b"\x50\x02" + struct.pack(">H", pkt_id)


def build_pubcomp(pkt_id):
    return b"\x70\x02" + struct.pack(">H", pkt_id)


def build_pingresp():
    return b"\xD0\x00"


def build_pingreq():
    return b"\xC0\x00"


def build_suback(pkt_id, codes):
    body = struct.pack(">H", pkt_id) + bytes(codes)
    return b"\x90" + encode_remaining_length(len(body)) + body


def build_publish(topic, payload, qos=0, pkt_id=1, retain=False):
    flags = ((qos & 3) << 1) | (1 if retain else 0)
    tb = topic.encode("utf-8")
    body = struct.pack(">H", len(tb)) + tb
    if qos:
        body += struct.pack(">H", pkt_id)
    pb = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    body += pb
    return bytes([0x30 | flags]) + encode_remaining_length(len(body)) + body


def build_connect(client_id, username=None, password=None, keepalive=30,
                  will_topic=None, will_payload=None, will_qos=1, will_retain=True):
    cflags = 0x02
    payload = struct.pack(">H", len(client_id)) + client_id.encode("utf-8")
    if will_topic is not None:
        cflags |= 0x04 | ((will_qos & 3) << 3) | (0x20 if will_retain else 0)
        payload += struct.pack(">H", len(will_topic)) + will_topic.encode("utf-8")
        wp = will_payload.encode("utf-8") if isinstance(will_payload, str) else will_payload
        payload += struct.pack(">H", len(wp)) + wp
    if username:
        cflags |= 0x80
        payload += struct.pack(">H", len(username)) + username.encode("utf-8")
    if password:
        cflags |= 0x40
        pb = password.encode("utf-8")
        payload += struct.pack(">H", len(pb)) + pb
    var = b"\x00\x04MQTT\x04" + bytes([cflags]) + struct.pack(">H", keepalive)
    body = var + payload
    return b"\x10" + encode_remaining_length(len(body)) + body


def build_subscribe(pkt_id, topics):
    body = struct.pack(">H", pkt_id)
    for t, q in topics:
        tb = t.encode("utf-8")
        body += struct.pack(">H", len(tb)) + tb + bytes([q & 3])
    return b"\x82" + encode_remaining_length(len(body)) + body