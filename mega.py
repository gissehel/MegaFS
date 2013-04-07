#!/usr/bin/env python
import sys

from megatools import MegaCommandLineClient

if __name__ == '__main__' :
    megaclparser = MegaCommandLineClient()
    if not(megaclparser.run( sys.argv )) :
        sys.exit(1)




