"""Home Wi-Fi transport. Endpoint comes from the owner's USB setup."""
import json
import socket


def auth_header(token):
    if token is None:
        return ""
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise ValueError("invalid pairing")
    return "Authorization: Bearer " + token + "\r\n"


def post_care(host, port, body, token=None):
    addr = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1]
    sock = socket.socket()
    try:
        sock.settimeout(5)
        sock.connect(addr)
        payload = json.dumps(body).encode()
        head = ("POST /api/pet-nest/care HTTP/1.0\r\nHost: %s:%d\r\n"
                "%sContent-Type: application/json\r\nContent-Length: %d\r\n"
                "Connection: close\r\n\r\n") % (host, port, auth_header(token), len(payload))
        sock.write(head.encode() + payload)
        line = sock.readline()
        code = int(line.split()[1])
        for i in range(40):
            if sock.readline() in (b"\r\n", b"\n"):
                break
        else:
            raise ValueError("response headers")
        data = bytearray()
        while True:
            part = sock.read(512)
            if not part:
                break
            data.extend(part)
            if len(data) > 8192:
                raise ValueError("large reply")
        if code in (400, 403, 404, 422):
            return {"rejected":True}
        if code != 200:
            raise OSError(code)
        return json.loads(data)
    finally:
        sock.close()


def read_profile(stream, pet_id):
    """Only accumulate one animal. The event/media arrays can be much larger than RAM."""
    try:
        from pet_mood import compact
    except ImportError:
        from .pet_mood import compact
    prefix = bytearray()
    found_array = False
    record = bytearray()
    depth = 0
    quoted = escaped = False
    while True:
        chunk = stream.read(512)
        if not chunk:
            raise ValueError("incomplete ecosystem")
        for b in chunk:
            if not found_array:
                if b not in (9,10,13,32):
                    prefix.append(b)
                if b == 91:
                    if prefix != b'{"pets":[':
                        raise ValueError("unknown ecosystem layout")
                    found_array = True
                if len(prefix) > 32:
                    raise ValueError("expected pets")
                continue
            if not depth:
                if b == 93:
                    return None
                if b in (9,10,13,32,44):
                    continue
                if b != 123:
                    raise ValueError("expected pet object")
            record.append(b)
            if len(record) > 16384:
                raise ValueError("large pet profile")
            if quoted:
                if escaped:
                    escaped = False
                elif b == 92:
                    escaped = True
                elif b == 34:
                    quoted = False
            elif b == 34:
                quoted = True
            elif b == 123:
                depth += 1
            elif b == 125:
                depth -= 1
                if depth == 0:
                    value = json.loads(bytes(record))
                    if value.get("pet_id") == pet_id:
                        return compact(value)
                    record = bytearray()


def get_profile(host, port, pet_id, token=None):
    addr = socket.getaddrinfo(host,port,0,socket.SOCK_STREAM)[0][-1]
    sock = socket.socket()
    try:
        sock.settimeout(4)
        sock.connect(addr)
        sock.write(("GET /api/pet-nest/ecosystem HTTP/1.0\r\nHost: %s:%d\r\n%sConnection: close\r\n\r\n" % (host,port,auth_header(token))).encode())
        if sock.readline().split()[1] != b"200":
            raise OSError("profile unavailable")
        for i in range(40):
            if sock.readline() in (b"\r\n",b"\n"):
                return read_profile(sock,pet_id)
        raise ValueError("response headers")
    finally:
        sock.close()
