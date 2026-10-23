import numpy as np
from .data import CLASSES, UrbanScene

def validate_scene(scene: UrbanScene) -> dict:
    arrays=(scene.red,scene.nir,scene.lst_c,scene.land_cover)
    if len({a.shape for a in arrays}) != 1 or scene.red.ndim != 2: raise ValueError("All inputs must be aligned 2D arrays")
    if not all(np.all(np.isfinite(a)) for a in arrays[:3]): raise ValueError("Reflectance and LST must be finite")
    if np.any(scene.red < 0) or np.any(scene.nir < 0): raise ValueError("Reflectance must be non-negative")
    # Class 0 marks pixels outside the study area (e.g. beyond a city boundary or under cloud).
    if not set(np.unique(scene.land_cover)).issubset({0, *CLASSES}): raise ValueError("Unknown land-cover class")
    if not np.any(scene.land_cover > 0): raise ValueError("No pixels inside the study area")
    return {"provenance":scene.provenance,"rows":int(scene.red.shape[0]),"columns":int(scene.red.shape[1]),"resolution_m":scene.resolution_m,"pixels":int(np.count_nonzero(scene.land_cover > 0))}

def derive_ndvi(red, nir):
    return np.divide(nir-red, nir+red, out=np.zeros_like(red,dtype=float), where=(nir+red)!=0)

def _regression(x,y,seed=9):
    slope, intercept=np.polyfit(x,y,1); predicted=slope*x+intercept; r2=1-np.sum((y-predicted)**2)/np.sum((y-y.mean())**2)
    rng=np.random.default_rng(seed); slopes=[]
    for _ in range(300):
        idx=rng.integers(0,len(x),len(x)); slopes.append(np.polyfit(x[idx],y[idx],1)[0])
    return {"slope_c_per_ndvi":round(float(slope),3),"intercept_c":round(float(intercept),3),"r_squared":round(float(r2),3),"bootstrap_slope_ci_95":[round(float(v),3) for v in np.percentile(slopes,[2.5,97.5])],"sample_size":int(len(x))}

def analyse_scene(scene: UrbanScene, sample_size=200):
    quality=validate_scene(scene); ndvi=derive_ndvi(scene.red,scene.nir); inside=scene.land_cover>0
    mean,sd=float(scene.lst_c[inside].mean()),float(scene.lst_c[inside].std())
    # Statistical screening bands: <=-1 SD, -1--.35, -.35--.35, .35-1, >=1 SD; 0 outside the study area.
    z=np.where(inside,(scene.lst_c-mean)/sd,0.0); uhi=np.where(inside,np.select([z<=-1,z<=-.35,z<.35,z<1],[1,2,3,4],default=5),0)
    candidates=np.flatnonzero(inside); rng=np.random.default_rng(77); idx=rng.choice(candidates,min(sample_size,candidates.size),replace=False); reg=_regression(ndvi.ravel()[idx],scene.lst_c.ravel()[idx])
    land=[]
    for code,name in CLASSES.items():
        values=scene.lst_c[scene.land_cover==code]; land.append({"class_id":code,"land_cover":name,"pixels":int(len(values)),"area_km2":round(len(values)*scene.resolution_m**2/1e6,3),"mean_lst_c":round(float(values.mean()),2),"p95_lst_c":round(float(np.percentile(values,95)),2),"mean_ndvi":round(float(ndvi[scene.land_cover==code].mean()),3)})
    uhi_rows=[]; names={1:"Cool island",2:"Low heat",3:"Moderate heat",4:"High heat",5:"Heat island core"}
    for code,name in names.items():
        pixels=int(np.count_nonzero(uhi==code)); uhi_rows.append({"uhi_class":name,"pixels":pixels,"area_km2":round(pixels*scene.resolution_m**2/1e6,3),"area_pct":round(pixels/candidates.size*100,2)})
    eligible=(scene.land_cover==1)&(uhi>=4)&(ndvi<.35)
    priority=np.where(eligible,np.maximum(z,0)*(1-np.clip(ndvi,0,1)),0.0)
    scenarios=[]
    for delta in (.05,.10,.15):
        estimates=np.array(reg["bootstrap_slope_ci_95"])*delta*-1
        scenarios.append({"ndvi_increase":delta,"eligible_built_up_area_km2":round(np.count_nonzero(eligible)*scene.resolution_m**2/1e6,3),"screening_cooling_c":round(float(-reg["slope_c_per_ndvi"]*delta),2),"bootstrap_cooling_range_c":[round(float(v),2) for v in sorted(estimates)]})
    summary={**quality,"analysis_scope":"Daytime surface-UHI intervention screening, not causal prediction, air temperature or health-risk measurement.","mean_lst_c":round(mean,2),"lst_sd_c":round(sd,2),"heat_island_core_area_pct":next(r["area_pct"] for r in uhi_rows if r["uhi_class"]=="Heat island core"),"eligible_intervention_pixels":int(np.count_nonzero(eligible)),"ndvi_lst_regression":reg}
    return ndvi,uhi,priority,land,uhi_rows,scenarios,summary
