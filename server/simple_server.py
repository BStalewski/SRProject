# Simple server for testing purpose

import socket

if __name__ == '__main__':
    s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
    port = 4321 # 1918
    ip = '192.168.1.11' #socket.gethostname()
    s.bind( (ip, port) )

    s.listen( 5 )
    while 1:
        (csocket, adr) = s.accept()
        print csocket.recv(100)
        csocket.close()

