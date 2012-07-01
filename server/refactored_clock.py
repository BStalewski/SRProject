from copy import deepcopy

class Clock:
    def __init__(self, my_nr, count):
        self.my_nr = my_nr
        self.clock = [ [0] * count for _ in range(count) ]

    #def refuse( self ):
    def refuse( self ):
        #self.clock[self.my_nr][sender] -= 1
        # comment in new clock without sender
        #self.clock[self.my_nr][self.my_nr] -= 1
        self.clock[self.my_nr][self.my_nr] -= 1

    def send( self ):
        self.clock[self.my_nr][self.my_nr] += 1
    
    def recv(self, sender_nr, clock_vec):
        self.clock[sender_nr] = clock_vec
        self.clock[self.my_nr][sender_nr] += 1
        self.clock[sender_nr][sender_nr] += 1
        #self.clock[self.my_nr][self.my_nr] += 1

    def get_vector(self):
        return deepcopy(self.clock[self.my_nr])

    def getColumn(self, sender_nr):
        return [vec[sender_nr] for vec in self.clock]

    def isSenderEarlier(self, sender_nr, sender_vec):
        my_vector = self.get_vector()
        is_earlier = False
        for (i, val) in enumerate(my_vector):
            if i == self.my_nr:
                continue
            is_earlier = is_earlier or val > sender_vec[i]

        return is_earlier


    def print_state(self):
        print 'Zegar nr', (self.my_nr + 1)
        for vec in self.clock:
            self.print_vec(vec)
    
    def print_vec(self, vec):
        print '|',
        for nr in vec:
            print '%4d' % nr,
        print '|'


