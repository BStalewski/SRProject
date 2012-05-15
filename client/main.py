from main import Client


if __name__ == '__main__':
    ip_file = 'ips.txt'
    port = 1918
    myNr = 2
    client = Client( ip_file, port, myNr )
    client.start()
