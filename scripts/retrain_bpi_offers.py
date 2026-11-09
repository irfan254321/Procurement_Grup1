import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from procurement.bpi_offer_retrain import retrain
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--iterations',type=int,default=350)
    a=p.parse_args();retrain(a.previous,a.out,a.iterations)
