from copy import deepcopy

class Clock:
    def __init__(self, myNr, count):
        self.myNr = myNr
        self.clock = [ [0] * count for _ in range(count) ]

    #def refuse( self ):
    def refuse( self ):
        #self.clock[self.myNr][sender] -= 1
        # comment in new clock without sender
        #self.clock[self.myNr][self.myNr] -= 1
        self.clock[self.myNr][self.myNr] -= 1

    def send( self ):
        self.clock[self.myNr][self.myNr] += 1
    
    def recv(self, senderNr, clockVec):
        self.clock[senderNr] = clockVec
        self.clock[self.myNr][senderNr] += 1
        self.clock[senderNr][senderNr] += 1
        #self.clock[self.myNr][self.myNr] += 1

    def getVector(self):
        return deepcopy(self.clock[self.myNr])

    def getColumn(self, senderNr):
        return [vec[senderNr] for vec in self.clock]

    def isSenderEarlier(self, senderNr, senderVec):
        myVector = self.getVector()
        isEarlier = False
        for (i, val) in enumerate(myVector):
            if i == self.myNr:
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

