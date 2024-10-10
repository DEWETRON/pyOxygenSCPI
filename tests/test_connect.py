import socket
import threading
import time
from pyOxygenSCPI import OxygenSCPI

TCP_PORT = 10001

class TestServer(threading.Thread):
    __test__ = False
    def __init__(self):
        super().__init__()
        self.ready = False

    def handle_ver(self, client):
        r = client.recv(1024).decode()
        assert r == '*VER?\n'
        client.sendall('SCPI,"1999.0",RC_SCPI,"1.21",PYTEST,"1.0.0"\n'.encode())

    def handle_idn(self, client):
        r = client.recv(1024).decode()
        assert r == '*IDN?\n'
        client.sendall('DEWETRON,PYTEST,0,1.0.0\n'.encode())

    def handle_init_sequence(self, client):
        r = client.recv(1024).decode()
        assert r == ':COMM:HEAD OFF\n'

        self.handle_ver(client)

        r = client.recv(1024).decode()
        assert r == ':NUM:NORMAL:ITEMS?\n'
        client.sendall(':NUM:ITEMS NONE\n'.encode())

        r = client.recv(1024).decode()
        assert r == ':NUM:NORMAL:NUMBER 0\n'

        r = client.recv(1024).decode()
        assert r == ':ELOG:ITEMS?\n'
        client.sendall(':ELOG:ITEMS NONE\n'.encode())

        r = client.recv(1024).decode()
        assert r == ':ELOG:TIM?\n'
        client.sendall(':ELOG:TIM ELOG\n'.encode())

        r = client.recv(1024).decode()
        assert r == ':ELOG:CALC?\n'
        client.sendall(':ELOG:CALC AVG\n'.encode())

    def handle_client(self, client):
        self.handle_init_sequence(client)
        self.handle_idn(client)

    def run(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_sock.bind(('127.0.0.1', TCP_PORT))
            server_sock.listen(0)
            self.ready = True
            client, _ = server_sock.accept()
            try:
                self.handle_client(client)
            finally:
                client.close()
            server_sock.close()
        except:
            pass
        self.ready = False

def test_connect_fails():
    client = OxygenSCPI('localhost', TCP_PORT)
    assert client.connect() == False

def test_connect():
    server_thread = TestServer()
    server_thread.start()
    time.sleep(0.2)
    assert server_thread.ready

    client = OxygenSCPI('localhost', TCP_PORT)
    assert client.connect() == True
    assert client.getVersion() == (1,21)
    assert client.getIdn() == 'DEWETRON,PYTEST,0,1.0.0'
    client.disconnect()

    server_thread.join()

#if __name__ == '__main__':
#    pytest.main()
