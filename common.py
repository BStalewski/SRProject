# Functions commond for client and server

def fillOutMsg( msg, msgSize ):
    missingSize = msgSize - len( msg )
    if missingSize < 0:
        raise RuntimeError('Message too big')
    filling = ''.join( [ '#' for _ in range( missingSize ) ] )
    return msg + filling
    
