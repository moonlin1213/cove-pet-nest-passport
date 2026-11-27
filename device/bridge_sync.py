"""Nonblocking small requests to the paired LAN bridge, advanced by the UI loop."""
import errno
import select
import socket
import time

class BridgeSync:
    def __init__(self):
        self.sock=None

    def close(self):
        if self.sock is not None:self.sock.close()
        self.sock=None

    def start(self,host,port,token,path,data,now):
        method='POST' if data else 'GET'
        self.out=(method+' /'+path+' HTTP/1.0\r\nHost: passport\r\nAuthorization: Bearer '+token+'\r\nContent-Length: '+str(len(data))+'\r\nConnection: close\r\n\r\n').encode()+data
        self.res=bytearray()
        self.started=now
        self.path=path
        self.sock=socket.socket()
        try:
            self.sock.setblocking(False)
            try:self.sock.connect((host,port))
            except OSError as e:
                if e.args[0] not in (errno.EINPROGRESS,errno.EAGAIN,114):raise
            self.poll=select.poll()
            self.poll.register(self.sock,select.POLLOUT)
        except Exception:
            self.close()
            raise

    def step(self,now):
        if time.ticks_diff(now,self.started)>5000:raise OSError('bridge timeout')
        if not self.poll.poll(0):return None
        if self.out:
            n=self.sock.send(self.out)
            if n:
                self.out=self.out[n:]
                if not self.out:self.poll.modify(self.sock,select.POLLIN)
            return None
        data=self.sock.recv(512)
        if data:
            self.res.extend(data)
            if len(self.res)>2000:raise ValueError('oversized bridge receipt')
            return None
        head,body=bytes(self.res).split(b'\r\n\r\n',1)
        lines=head.split(b'\r\n')
        if lines[0].split()[1]!=b'200':raise OSError('bridge unavailable')
        if not any(line.lower()==b'content-length: '+str(len(body)).encode() for line in lines[1:]):
            raise ValueError('incomplete bridge receipt')
        self.close()
        return body
