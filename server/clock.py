from copy import deepcopy

class Clock:
    def __init__(self, myNr):
        self.myNr = myNr
        self.clock = [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
        ]

    def send( self ):
        self.clock[self.myNr][self.myNr] += 1
    
    def recv(self, nr, clockVec):
        innerNr = nr - 1
        self.clock[innerNr] = clockVec
        self.clock[self.myNr][innerNr] = clockVec[innerNr]
        self.clock[self.myNr][self.myNr] += 1

    def getVector(self):
        return deepcopy(self.clock[self.myNr])

    def printState(self):
        print 'Zegar nr', (self.myNr + 1)
        for vec in self.clock:
            self.printVec(vec)
    
    def printVec(self, vec):
        print '|',
        for nr in vec:
            print '%4d' % nr,
        print '|'


class ClockSet:
    def __init__(self, clocksNr):
        self.clocks = [Clock(i) for i in range(clocksNr)]

    def clockSend(self, nr, disconnected=[]):
        innerNr = nr - 1
        self.clocks[innerNr].send()
        clockVec = self.clocks[innerNr].getVector()
        for i in range( len(self.clocks) ):
            if i != innerNr:
                if (i+1) in disconnected:
                    print 'Zegar nr %d nie otrzymal' % (i+1)
                else:
                    self.clocks[i].recv(nr, clockVec)

    def printClocks(self):
        for clock in self.clocks:
            clock.printState()

if __name__ == '__main__':
    clockSet = ClockSet(4)

    print 'Stan 0'
    clockSet.printClocks()

    print 'S1.send'
    clockSet.clockSend(1)
    clockSet.printClocks()

    print 'S4.send'
    clockSet.clockSend(4)
    clockSet.printClocks()

    print 'S3.send'
    clockSet.clockSend(3)
    clockSet.printClocks()

    print 'S2.send'
    clockSet.clockSend(2)
    clockSet.printClocks()

    print 'S1.send'
    clockSet.clockSend(1, disconnected=[2])
    clockSet.printClocks()

    print 'S1.send'
    clockSet.clockSend(1, disconnected=[2])
    clockSet.printClocks()

