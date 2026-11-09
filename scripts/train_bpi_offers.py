import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from procurement.bpi_offers import train
from procurement.bpi import DEFAULT_DB,ROOT
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=DEFAULT_DB)
    p.add_argument('--out',type=Path,default=ROOT/'runs'/'bpi_offers')
    p.add_argument('--iterations',type=int,default=150)
    p.add_argument('--max-train',type=int,default=30000)
    a=p.parse_args();train(a.source,a.out,iterations=a.iterations,max_train=a.max_train)
