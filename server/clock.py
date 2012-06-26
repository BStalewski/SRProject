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
        senderNr = nr - 1
        self.clock[senderNr] = clockVec
        self.clock[self.myNr][senderNr] += 1
        self.clock[self.myNr][self.myNr] += 1

    def getVector(self):
        return deepcopy(self.clock[self.myNr])

    def getColumn(self, nr):
        senderNr = nr - 1
        return [vec[senderNr] for vec in self.clock]

    def isSenderEarlier(self, nr, senderVec):
        senderNr = nr - 1
        myVector = self.getVector()
        isEarlier = False
        for (i, val) in enumerate(myVector):
            if i == senderNr:
                continue
            isEarlier = isEarlier or val > senderVec[i]

        return isEarlier


    def printState(self):
        print 'Zegar nr', (self.myNr + 1)
        for vec in self.clock:
            self.printVec(vec)
    
    def printVec(self, vec):
        print '|',
        for nr in vec:
            print '%4d' % nr,
        print '|'

