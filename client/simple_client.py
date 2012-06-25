import socket

if __name__ == '__main__':
    ip_file = 'ips.txt'
    ip = '127.0.0.1' #'192.168.1.14'

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, 4455))
    msg = ''.join([ 'A' for _ in range(100) ])
    s.send( msg )
    s.close()
