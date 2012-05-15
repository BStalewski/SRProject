# Module for logging information

class Logger:
    def __init__( self, level ):
        self.level = level

    def log( self, msg, msgLevel ):
        if msgLevel >= self.level:
            print msg

