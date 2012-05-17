from client import Client


if __name__ == '__main__':
    ip_file = 'ips.txt'
    port = 4321
    myNr = 2
    client = Client( ip_file, port, myNr )
    client.start()
