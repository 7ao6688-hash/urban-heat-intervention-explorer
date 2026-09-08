from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from urban_heat_explorer.demo import run_demo
if __name__=="__main__":
    for k,v in run_demo(root/'output'/'demo').items(): print(f"{k}: {v}")
