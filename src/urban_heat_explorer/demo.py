import csv,json
from pathlib import Path
import numpy as np
from .analysis import analyse_scene
from .data import UrbanScene,make_synthetic_scene

def _json(x,p): p.write_text(json.dumps(x,indent=2)+"\n",encoding="utf-8"); return p
def _csv(rows,p):
    with p.open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    return p
def run_scene(scene, output_dir="output/analysis"):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True); ndvi,uhi,priority,land,uhi_rows,scenarios,summary=analyse_scene(scene)
    np.savez_compressed(out/"intervention_priority.npz",priority_score=priority,ndvi=ndvi,uhi_class=uhi)
    return {"land_cover":_csv(land,out/"land_cover_statistics.csv"),"uhi":_csv(uhi_rows,out/"uhi_area_statistics.csv"),"scenarios":_json(scenarios,out/"cooling_scenarios.json"),"regression":_json(summary["ndvi_lst_regression"],out/"ndvi_lst_regression.json"),"summary":_json(summary,out/"summary.json")}

def run_demo(output_dir="output/demo"):
    out=Path(output_dir); scene=make_synthetic_scene();out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/"synthetic_scene.npz",red=scene.red,nir=scene.nir,lst_c=scene.lst_c,land_cover=scene.land_cover)
    return run_scene(scene,out)
