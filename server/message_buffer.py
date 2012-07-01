import logging
import threading
from collections import deque

logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )

class MessageBuffer:
    def __init__( self ):
        self.buf = deque()
        self.logger = logging.getLogger('[BUFFER]')
        self.lock = threading.Lock()

    def can_be_removed( self, msg, col ):
        nr = msg['sender']
        self.logger.log('Trying to remove msg from the buffer')
        self.logger.log('Sender column in my column:', col, 'Sender nr:', nr, 'Msg clocks:', msg['clocks'])
        self.logger.log('Checking if min(col) > msg[clocks][nr] :: ', min(col), '>', msg['clocks'][nr])

        return min( col ) > msg['clocks'][nr] 

    def update( self, msg, clock ):
        def is_not_needed( m ):
            sender  = m['sender']
            return self.can_be_removed( m, clock.getColumn( sender ) )

        self.lock.acquire()
        self.buf.append( msg )
        to_remove = [ i for (i, m) in enumerate(self.buf) if is_not_needed( m ) ]
        to_remove.reverse()

        for i in to_remove:
            self.logger.debug('Message discarded')
            del self.buf[ i ]

        self.lock.release()
        self.logger.debug( '%d remaining message(s) in the buffer' % len(self.buf) )

    def remove( self, clocks, sender ):
        self.get_message( clocks, sender )

    def find( self, clocks, sender ):
        return self.get_message( clocks, sender, remove=False )

    def is_in_buffer( self, clocks, sender ):
        return self.get_message( clocks, sender, remove=False ) is not None

    def get_message( self, clocks, sender, remove=True ):
        self.lock.acquire()
        matching_msgs = filter( lambda m: m['clocks'] == clocks and m['sender'] == sender, self.buf )
        try:
            found_msg = matching_msgs[0]
        except IndexError:
            found_msg = None

        if found_msg and remove:
            self.buf.remove( found_msg )

        self.lock.release()
        return found_msg

    def get_last_messages( self, sender_nr, msg_count ):
        self.lock.acquire()
        msgs = filter( lambda m: m['sender'] == sender_nr, self.buf )[:msg_count]
        self.lock.release()

        return msgs

