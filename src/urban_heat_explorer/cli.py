import argparse
import numpy as np
from .data import UrbanScene
from .demo import run_demo, run_scene
def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True); d=s.add_parser("demo");d.add_argument("--output-dir",default="output/demo"); q=s.add_parser("analyse");q.add_argument("input");q.add_argument("--output-dir",default="output/analysis"); a=p.parse_args()
    if a.cmd=="demo":
        for k,v in run_demo(a.output_dir).items(): print(f"{k}: {v}")
    else:
        with np.load(a.input) as z: scene=UrbanScene(z["red"],z["nir"],z["lst_c"],z["land_cover"])
        for k,v in run_scene(scene,a.output_dir).items(): print(f"{k}: {v}")
