from pathlib import Path
import csv, json, random, math, textwrap
from datetime import datetime, timedelta

ROOT = Path('/mnt/data/Centrifugal_Pump_KBS')
DATA = ROOT/'data'
SRC = ROOT/'src'
TESTS = ROOT/'tests'
for p in [DATA,SRC,TESTS]: p.mkdir(parents=True, exist_ok=True)

components = [
('C01','Pump Casing','Hydraulic','Contains fluid and converts velocity to pressure.'),
('C02','Impeller','Hydraulic','Transfers rotational energy to the fluid.'),
('C03','Shaft','Mechanical','Transmits torque from driver to impeller.'),
('C04','Bearings','Mechanical','Support shaft and control radial/axial movement.'),
('C05','Mechanical Seal','Sealing','Limits leakage along the rotating shaft.'),
('C06','Coupling','Mechanical','Connects motor shaft to pump shaft.'),
('C07','Suction Line / Strainer','Hydraulic','Supplies liquid to pump inlet.'),
('C08','Discharge Line / Valve','Hydraulic','Controls pump discharge flow.'),
('C09','Electric Motor','Electrical','Provides mechanical drive power.'),
('C10','Baseplate / Foundation','Structural','Maintains alignment and structural rigidity.'),
]

faults = [
('F01','Bearing Wear / Failure','C04','HIGH','Medium','Medium','Progressive bearing damage or lubrication-related distress.'),
('F02','Cavitation','C02','HIGH','Low','Medium','Vapor bubble formation/collapse due to inadequate suction conditions.'),
('F03','Shaft Misalignment','C03','HIGH','Medium','Medium','Pump and motor shaft centerlines are not correctly aligned.'),
('F04','Impeller Blockage / Fouling','C02','MEDIUM','Low','Medium','Deposits or foreign material restrict impeller passages.'),
('F05','Mechanical Seal Failure','C05','HIGH','Medium','Medium','Seal faces or elastomers are worn, damaged, or thermally distressed.'),
('F06','Suction Blockage / Clogged Strainer','C07','HIGH','Low','Low','Restriction on suction side reduces available flow and inlet pressure.'),
('F07','Dry Running / Loss of Prime','C01','CRITICAL','Medium','High','Pump operates with insufficient liquid, causing loss of cooling/lubrication.'),
('F08','Motor Overload','C09','HIGH','Medium','Medium','Driver current/power exceeds expected operating condition.'),
('F09','Coupling Damage / Looseness','C06','HIGH','Medium','Medium','Flexible element wear, looseness, or coupling damage.'),
('F10','Impeller Damage / Erosion','C02','HIGH','High','High','Impeller surfaces are eroded, cracked, or otherwise mechanically damaged.'),
('F11','Discharge Restriction / Closed Valve','C08','HIGH','Low','Low','Excessive discharge-side restriction moves pump toward low-flow operation.'),
('F12','Air Ingress on Suction Side','C07','HIGH','Low','Medium','Air enters suction piping or fittings and disrupts hydraulic performance.'),
('F13','Base / Foundation Looseness','C10','MEDIUM','Medium','Medium','Loose hold-down bolts, soft foot, or weak foundation increases vibration.'),
('F14','Electrical Supply Imbalance','C09','HIGH','Medium','Medium','Voltage/current phase imbalance causes motor heating and unstable operation.'),
]

symptoms = [
('S01','High overall vibration','vibration_high','Mechanical'),
('S02','Bearing temperature high','bearing_temp_high','Thermal'),
('S03','Abnormal grinding/rumbling noise','grinding_noise','Acoustic'),
('S04','Crackling / gravel-like noise','crackling_noise','Acoustic'),
('S05','Low discharge pressure','discharge_pressure_low','Hydraulic'),
('S06','Low flow rate','flow_low','Hydraulic'),
('S07','Low suction pressure / high vacuum','suction_pressure_low','Hydraulic'),
('S08','Visible seal leakage','seal_leakage','Visual'),
('S09','Motor current high','motor_current_high','Electrical'),
('S10','Motor temperature high','motor_temp_high','Thermal'),
('S11','Pressure fluctuating','pressure_fluctuation','Hydraulic'),
('S12','Flow fluctuating','flow_fluctuation','Hydraulic'),
('S13','No / near-zero flow','no_flow','Hydraulic'),
('S14','Pump fails to prime','prime_failure','Operational'),
('S15','Shaft/coupling vibration dominant','coupling_vibration','Mechanical'),
('S16','Seal area temperature high','seal_temp_high','Thermal'),
('S17','Discharge pressure unusually high','discharge_pressure_high','Hydraulic'),
('S18','Motor speed unstable','speed_unstable','Electrical'),
('S19','Localized baseplate vibration','base_vibration','Mechanical'),
('S20','Air bubbles / frothy discharge','air_bubbles','Visual'),
('S21','Efficiency / developed head reduced','efficiency_low','Performance'),
('S22','Rapid temperature rise with low flow','rapid_temp_rise','Thermal'),
]

# weights 1..5; negative weights are contradiction evidence
W = {
'F01': {'vibration_high':5,'bearing_temp_high':5,'grinding_noise':4,'motor_current_high':2,'efficiency_low':1},
'F02': {'crackling_noise':5,'vibration_high':4,'discharge_pressure_low':3,'flow_low':3,'suction_pressure_low':5,'pressure_fluctuation':4,'flow_fluctuation':4,'efficiency_low':3},
'F03': {'vibration_high':5,'coupling_vibration':5,'bearing_temp_high':3,'motor_current_high':2,'grinding_noise':2},
'F04': {'flow_low':5,'discharge_pressure_low':4,'efficiency_low':5,'vibration_high':2,'motor_current_high':2},
'F05': {'seal_leakage':5,'seal_temp_high':4,'vibration_high':2,'bearing_temp_high':1},
'F06': {'suction_pressure_low':5,'flow_low':5,'discharge_pressure_low':4,'crackling_noise':2,'efficiency_low':3},
'F07': {'no_flow':5,'prime_failure':5,'rapid_temp_rise':5,'seal_temp_high':4,'bearing_temp_high':3,'grinding_noise':2},
'F08': {'motor_current_high':5,'motor_temp_high':5,'vibration_high':2,'speed_unstable':2,'flow_low':1},
'F09': {'coupling_vibration':5,'vibration_high':4,'grinding_noise':3,'bearing_temp_high':2},
'F10': {'vibration_high':4,'flow_low':4,'discharge_pressure_low':4,'efficiency_low':5,'grinding_noise':2},
'F11': {'discharge_pressure_high':5,'flow_low':5,'rapid_temp_rise':4,'motor_current_high':2,'efficiency_low':2},
'F12': {'air_bubbles':5,'prime_failure':3,'flow_fluctuation':4,'pressure_fluctuation':4,'discharge_pressure_low':3,'flow_low':3},
'F13': {'base_vibration':5,'vibration_high':4,'coupling_vibration':2,'grinding_noise':1},
'F14': {'motor_temp_high':5,'motor_current_high':4,'speed_unstable':4,'vibration_high':2},
}

actions = [
('A01','Inspect bearing lubrication and condition','F01','1','LOW','LOW','Check lubricant level/condition and bearing noise/temperature before replacement.'),
('A02','Replace damaged bearing','F01','2','MEDIUM','MEDIUM','Replace bearing if inspection confirms wear, spalling, seizure, or excessive clearance.'),
('A03','Improve suction conditions / verify NPSH margin','F02','1','LOW','MEDIUM','Check liquid level, suction losses, temperature, valves, and suction piping restrictions.'),
('A04','Inspect impeller for cavitation erosion','F02','2','MEDIUM','MEDIUM','Inspect impeller surfaces if cavitation persists or performance has degraded.'),
('A05','Laser/dial align motor and pump shafts','F03','1','MEDIUM','MEDIUM','Correct angular/parallel misalignment after verifying soft foot and pipe strain.'),
('A06','Clean impeller and internal passages','F04','1','LOW','MEDIUM','Isolate pump and remove deposits or foreign material from impeller passages.'),
('A07','Inspect/replace mechanical seal','F05','1','MEDIUM','MEDIUM','Inspect seal faces, flush plan, elastomers, shaft sleeve, and replace damaged seal parts.'),
('A08','Clean suction strainer and inspect suction line','F06','1','LOW','LOW','Remove blockage; verify suction valve is open and piping is unobstructed.'),
('A09','Stop pump and restore prime/liquid supply','F07','1','LOW','HIGH','Do not continue dry operation; restore liquid and investigate why prime was lost.'),
('A10','Inspect motor load and process operating point','F08','1','LOW','MEDIUM','Compare current/load to expected duty; check mechanical drag and process overload.'),
('A11','Inspect and repair/replace coupling elements','F09','1','MEDIUM','MEDIUM','Check coupling wear, looseness, fasteners, flexible elements, and alignment.'),
('A12','Inspect/repair or replace impeller','F10','1','HIGH','HIGH','Open pump after isolation; inspect erosion, cracks, blade damage, and clearances.'),
('A13','Open/verify discharge valve and minimum-flow path','F11','1','LOW','LOW','Correct excessive discharge restriction and avoid prolonged near-zero-flow operation.'),
('A14','Leak-test suction piping and fittings','F12','1','LOW','MEDIUM','Tighten fittings/gaskets and inspect suction line for air ingress.'),
('A15','Inspect hold-down bolts, soft foot and foundation','F13','1','MEDIUM','MEDIUM','Tighten/repair base, correct soft foot, and verify grouting/foundation integrity.'),
('A16','Check phase voltage/current balance and connections','F14','1','MEDIUM','MEDIUM','Qualified electrical personnel should inspect phase balance, terminals, and supply.'),
]

# Explicit higher-order rules (conditions ANDed)
rules = [
{'id':'R01','conditions':['vibration_high','bearing_temp_high','grinding_noise'],'fault_id':'F01','bonus':4,'explanation':'High vibration + hot bearing + rumbling/grinding strongly supports bearing distress.'},
{'id':'R02','conditions':['crackling_noise','suction_pressure_low','pressure_fluctuation'],'fault_id':'F02','bonus':5,'explanation':'Crackling noise with poor suction condition and pressure fluctuation is characteristic of cavitation.'},
{'id':'R03','conditions':['coupling_vibration','vibration_high','bearing_temp_high'],'fault_id':'F03','bonus':4,'explanation':'Coupling-dominant vibration with heating is consistent with shaft misalignment.'},
{'id':'R04','conditions':['flow_low','discharge_pressure_low','efficiency_low'],'fault_id':'F04','bonus':4,'explanation':'Low flow/head and reduced efficiency can indicate impeller fouling or blockage.'},
{'id':'R05','conditions':['seal_leakage','seal_temp_high'],'fault_id':'F05','bonus':5,'explanation':'Leakage together with elevated seal-area temperature strongly supports seal failure.'},
{'id':'R06','conditions':['suction_pressure_low','flow_low','discharge_pressure_low'],'fault_id':'F06','bonus':4,'explanation':'Poor suction pressure with low flow/head supports suction restriction.'},
{'id':'R07','conditions':['no_flow','prime_failure','rapid_temp_rise'],'fault_id':'F07','bonus':7,'explanation':'Loss of prime/no flow with rapid heating is a critical dry-running pattern.'},
{'id':'R08','conditions':['motor_current_high','motor_temp_high'],'fault_id':'F08','bonus':5,'explanation':'High current with motor heating supports overload.'},
{'id':'R09','conditions':['coupling_vibration','grinding_noise'],'fault_id':'F09','bonus':4,'explanation':'Coupling vibration plus mechanical noise supports coupling damage/looseness.'},
{'id':'R10','conditions':['flow_low','discharge_pressure_low','vibration_high','efficiency_low'],'fault_id':'F10','bonus':4,'explanation':'Reduced hydraulic performance plus vibration can result from impeller damage/erosion.'},
{'id':'R11','conditions':['discharge_pressure_high','flow_low','rapid_temp_rise'],'fault_id':'F11','bonus':6,'explanation':'High discharge pressure, low flow and rapid heating support excessive discharge restriction.'},
{'id':'R12','conditions':['air_bubbles','flow_fluctuation','pressure_fluctuation'],'fault_id':'F12','bonus':5,'explanation':'Air bubbles with unstable flow/pressure support suction-side air ingress.'},
{'id':'R13','conditions':['base_vibration','vibration_high'],'fault_id':'F13','bonus':5,'explanation':'Localized base vibration with high overall vibration supports foundation/base looseness.'},
{'id':'R14','conditions':['motor_temp_high','speed_unstable','motor_current_high'],'fault_id':'F14','bonus':5,'explanation':'Motor heating, unstable speed and abnormal current support electrical supply imbalance.'},
]

# CSV writers
def write_csv(path, header, rows):
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(header); w.writerows(rows)

write_csv(DATA/'components.csv',['component_id','component_name','category','description'],components)
write_csv(DATA/'faults.csv',['fault_id','fault_name','component_id','safety_priority','repair_cost','downtime','description'],faults)
write_csv(DATA/'symptoms.csv',['symptom_id','symptom_name','key','category'],symptoms)
write_csv(DATA/'maintenance_actions.csv',['action_id','action','fault_id','sequence','cost','downtime','details'],actions)

weight_rows=[]
for fid, m in W.items():
    for key,wt in m.items(): weight_rows.append((fid,key,wt))
write_csv(DATA/'symptom_fault_weights.csv',['fault_id','symptom_key','weight'],weight_rows)
with open(DATA/'rules.json','w',encoding='utf-8') as f: json.dump(rules,f,indent=2)

# Generate synthetic diagnostic cases
random.seed(359)
all_keys=[s[2] for s in symptoms]
case_rows=[]
for i in range(1,281):
    fid=random.choice(list(W))
    positives=set(W[fid].keys())
    observed={}
    for k in all_keys:
        if k in positives:
            p=min(0.92,0.38+0.10*W[fid][k])
        else:
            p=0.05
        observed[k]=1 if random.random()<p else 0
    # ensure at least 2 primary evidence items
    primary=sorted(W[fid], key=W[fid].get, reverse=True)[:3]
    for k in random.sample(primary, k=2): observed[k]=1
    missing_rate=random.choice([0,0,0.05,0.10,0.15])
    known=sum(1 for _ in all_keys if random.random()>missing_rate)
    case_rows.append([f'CASE-{i:03d}',fid,missing_rate,known]+[observed[k] for k in all_keys])
write_csv(DATA/'diagnostic_cases.csv',['case_id','true_fault_id','simulated_missing_rate','known_feature_count']+all_keys,case_rows)

# Generate synthetic operational sensor log with labeled episodes
start=datetime(2026,9,1,8,0)
episodes=[('NORMAL',40),('F02',35),('NORMAL',25),('F01',35),('NORMAL',25),('F12',30),('F11',30),('NORMAL',20),('F07',15)]
rows=[]; idx=0
for label,n in episodes:
    for _ in range(n):
        ts=start+timedelta(minutes=5*idx); idx+=1
        vib=random.gauss(2.4,0.35); btemp=random.gauss(58,2.5); mtemp=random.gauss(63,3)
        flow=random.gauss(100,3); dp=random.gauss(5.0,0.12); sp=random.gauss(1.25,0.05)
        current=random.gauss(32,1.2); sealtemp=random.gauss(55,2); fluct=random.gauss(2,0.7)
        noise=0; bubbles=0; prime=1
        if label=='F02':
            vib=random.gauss(6.8,0.7); flow=random.gauss(80,6); dp=random.gauss(4.1,0.3); sp=random.gauss(0.55,0.12); fluct=random.gauss(14,3); noise=1
        elif label=='F01':
            vib=random.gauss(8.2,0.9); btemp=random.gauss(86,5); current=random.gauss(36,1.5); noise=1
        elif label=='F12':
            flow=random.gauss(77,7); dp=random.gauss(4.0,0.35); fluct=random.gauss(17,4); bubbles=1; prime=1 if random.random()>0.2 else 0
        elif label=='F11':
            flow=random.gauss(35,7); dp=random.gauss(6.5,0.3); current=random.gauss(35,1.3); btemp=random.gauss(72,4); mtemp=random.gauss(75,4)
        elif label=='F07':
            flow=max(0,random.gauss(3,2)); dp=max(0,random.gauss(0.4,0.2)); sp=random.gauss(0.2,0.05); btemp=random.gauss(94,5); sealtemp=random.gauss(100,7); prime=0; noise=1
        rows.append([ts.isoformat(timespec='minutes'),round(vib,2),round(btemp,1),round(mtemp,1),round(flow,1),round(dp,2),round(sp,2),round(current,1),round(sealtemp,1),round(fluct,1),noise,bubbles,prime,label])
write_csv(DATA/'operational_sensor_log.csv',['timestamp','vibration_mm_s_rms','bearing_temp_c','motor_temp_c','flow_percent_of_baseline','discharge_pressure_bar','suction_pressure_bar_abs','motor_current_a','seal_temp_c','pressure_fluctuation_percent','abnormal_noise','air_bubbles','prime_ok','episode_label'],rows)

# source files
inference = r'''from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SAFETY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def load_knowledge():
    faults = pd.read_csv(DATA / "faults.csv")
    weights = pd.read_csv(DATA / "symptom_fault_weights.csv")
    actions = pd.read_csv(DATA / "maintenance_actions.csv")
    symptoms = pd.read_csv(DATA / "symptoms.csv")
    with open(DATA / "rules.json", encoding="utf-8") as f:
        rules = json.load(f)
    return faults, weights, actions, symptoms, rules


def derive_symptoms(sensor):
    """Convert numeric readings into symbolic evidence.
    Thresholds are prototype defaults for this academic demo, not OEM safety limits.
    """
    e = set()
    v = sensor.get
    if v("vibration_mm_s_rms") is not None and v("vibration_mm_s_rms") >= 6.0: e.add("vibration_high")
    if v("bearing_temp_c") is not None and v("bearing_temp_c") >= 80: e.add("bearing_temp_high")
    if v("motor_temp_c") is not None and v("motor_temp_c") >= 80: e.add("motor_temp_high")
    if v("flow_percent_of_baseline") is not None and v("flow_percent_of_baseline") < 75: e.add("flow_low")
    if v("flow_percent_of_baseline") is not None and v("flow_percent_of_baseline") < 10: e.add("no_flow")
    if v("discharge_pressure_bar") is not None and v("discharge_pressure_bar") < 4.2: e.add("discharge_pressure_low")
    if v("discharge_pressure_bar") is not None and v("discharge_pressure_bar") > 6.0: e.add("discharge_pressure_high")
    if v("suction_pressure_bar_abs") is not None and v("suction_pressure_bar_abs") < 0.70: e.add("suction_pressure_low")
    if v("motor_current_a") is not None and v("motor_current_a") > 38: e.add("motor_current_high")
    if v("seal_temp_c") is not None and v("seal_temp_c") >= 85: e.add("seal_temp_high")
    if v("pressure_fluctuation_percent") is not None and v("pressure_fluctuation_percent") >= 10:
        e.update(["pressure_fluctuation","flow_fluctuation"])
    if v("abnormal_noise"): e.add("grinding_noise")
    if v("crackling_noise"): e.add("crackling_noise")
    if v("air_bubbles"): e.add("air_bubbles")
    if v("seal_leakage"): e.add("seal_leakage")
    if v("coupling_vibration"): e.add("coupling_vibration")
    if v("base_vibration"): e.add("base_vibration")
    if v("speed_unstable"): e.add("speed_unstable")
    if v("efficiency_low"): e.add("efficiency_low")
    if v("rapid_temp_rise"): e.add("rapid_temp_rise")
    if v("prime_ok") is False: e.add("prime_failure")
    return e


def diagnose(evidence, top_n=5):
    faults, weights, actions, symptoms, rules = load_knowledge()
    evidence = set(evidence)
    results = []
    trace = []
    for _, fault in faults.iterrows():
        fid = fault.fault_id
        fw = weights[weights.fault_id == fid]
        max_score = fw.weight.clip(lower=0).sum() + sum(r.get("bonus",0) for r in rules if r["fault_id"] == fid)
        score = 0.0
        matched = []
        for _, row in fw.iterrows():
            if row.symptom_key in evidence:
                score += float(row.weight)
                matched.append((row.symptom_key, float(row.weight)))
        fired = []
        for rule in rules:
            if rule["fault_id"] == fid and all(c in evidence for c in rule["conditions"]):
                score += float(rule.get("bonus",0))
                fired.append(rule)
        confidence = 0 if max_score <= 0 else min(100.0, 100.0 * score / max_score)
        coverage = 0 if len(fw)==0 else 100.0 * len(matched)/len(fw)
        result = {
            "fault_id": fid,
            "fault": fault.fault_name,
            "component": fault.component_id,
            "safety_priority": fault.safety_priority,
            "repair_cost": fault.repair_cost,
            "downtime": fault.downtime,
            "score": round(score,2),
            "confidence": round(confidence,1),
            "coverage": round(coverage,1),
            "matched_evidence": [m[0] for m in sorted(matched,key=lambda x:x[1], reverse=True)],
            "fired_rules": [r["id"] for r in fired],
            "rule_explanations": [r["explanation"] for r in fired],
        }
        results.append(result)
    results.sort(key=lambda r: (r["confidence"], SAFETY_RANK.get(r["safety_priority"],0), r["score"]), reverse=True)
    for r in results[:top_n]:
        fa = actions[actions.fault_id == r["fault_id"]].sort_values("sequence")
        r["actions"] = fa[["action","cost","downtime","details"]].to_dict("records")
        trace.append({"fault":r["fault"],"evidence":r["matched_evidence"],"rules":r["fired_rules"],"confidence":r["confidence"]})
    return results[:top_n], trace


def diagnose_from_sensor(sensor, manual_evidence=None, top_n=5):
    evidence = derive_symptoms(sensor)
    if manual_evidence:
        evidence.update(manual_evidence)
    return diagnose(evidence, top_n=top_n), evidence
'''
(SRC/'inference_engine.py').write_text(inference,encoding='utf-8')

app = r'''import streamlit as st
import pandas as pd
from inference_engine import diagnose_from_sensor, load_knowledge

st.set_page_config(page_title="Centrifugal Pump KBS", page_icon="⚙️", layout="wide")
st.title("⚙️ Centrifugal Pump Fault Diagnosis KBS")
st.caption("CT-359 Knowledge Based System — academic prototype. Thresholds are demo defaults, not OEM safety limits.")

faults, weights, actions, symptoms, rules = load_knowledge()

with st.sidebar:
    st.header("Project Information")
    st.write("**Representation:** weighted production rules")
    st.write("**Inference:** forward chaining + evidence ranking")
    st.write("**Output:** fault ranking, explanation trace, maintenance advice")
    st.warning("For education only. Do not use as a real plant safety system.")

st.subheader("1. Sensor / operating evidence")
c1,c2,c3,c4 = st.columns(4)
with c1:
    vibration = st.number_input("Vibration (mm/s RMS)",0.0,30.0,2.5,0.1)
    bearing_temp = st.number_input("Bearing temperature (°C)",0.0,150.0,60.0,1.0)
    seal_temp = st.number_input("Seal-area temperature (°C)",0.0,150.0,55.0,1.0)
with c2:
    flow = st.number_input("Flow (% of healthy baseline)",0.0,150.0,100.0,1.0)
    discharge_p = st.number_input("Discharge pressure (bar)",0.0,20.0,5.0,0.1)
    suction_p = st.number_input("Suction pressure (bar abs)",0.0,5.0,1.25,0.05)
with c3:
    motor_current = st.number_input("Motor current (A)",0.0,200.0,32.0,1.0)
    motor_temp = st.number_input("Motor temperature (°C)",0.0,180.0,63.0,1.0)
    pressure_fluct = st.number_input("Pressure fluctuation (%)",0.0,100.0,2.0,1.0)
with c4:
    abnormal_noise = st.checkbox("Grinding/rumbling noise")
    crackling_noise = st.checkbox("Crackling/gravel-like noise")
    bubbles = st.checkbox("Air bubbles/frothy discharge")
    prime_ok = st.checkbox("Pump is primed", value=True)

st.subheader("2. Additional observed symptoms")
manual_labels = {
"seal_leakage":"Visible seal leakage",
"coupling_vibration":"Coupling-dominant vibration",
"base_vibration":"Localized baseplate vibration",
"speed_unstable":"Motor speed unstable",
"efficiency_low":"Reduced head/efficiency",
"rapid_temp_rise":"Rapid temperature rise at low flow",
}
manual=[]
cols=st.columns(3)
for i,(key,label) in enumerate(manual_labels.items()):
    if cols[i%3].checkbox(label): manual.append(key)

sensor = {
"vibration_mm_s_rms":vibration,"bearing_temp_c":bearing_temp,"seal_temp_c":seal_temp,
"flow_percent_of_baseline":flow,"discharge_pressure_bar":discharge_p,"suction_pressure_bar_abs":suction_p,
"motor_current_a":motor_current,"motor_temp_c":motor_temp,"pressure_fluctuation_percent":pressure_fluct,
"abnormal_noise":abnormal_noise,"crackling_noise":crackling_noise,"air_bubbles":bubbles,"prime_ok":prime_ok,
}

if st.button("Diagnose Fault", type="primary", use_container_width=True):
    (results, trace), evidence = diagnose_from_sensor(sensor, manual)
    st.subheader("3. Inferred evidence")
    st.write(", ".join(sorted(evidence)) if evidence else "No abnormal evidence detected.")
    if not evidence:
        st.success("No fault pattern has enough evidence from the entered observations.")
    else:
        st.subheader("4. Ranked diagnosis")
        df = pd.DataFrame([{k:r[k] for k in ["fault","confidence","safety_priority","repair_cost","downtime"]} for r in results])
        st.dataframe(df, use_container_width=True, hide_index=True)
        best=results[0]
        if best["safety_priority"] == "CRITICAL": st.error(f"CRITICAL: {best['fault']} — stop/secure equipment according to site procedures.")
        elif best["safety_priority"] == "HIGH": st.warning(f"Highest ranked: {best['fault']} ({best['confidence']}% evidence score)")
        else: st.info(f"Highest ranked: {best['fault']} ({best['confidence']}% evidence score)")
        st.subheader("5. Explanation and maintenance recommendations")
        for r in results[:3]:
            with st.expander(f"{r['fault']} — {r['confidence']}%", expanded=(r is best)):
                st.write("**Matched evidence:**", ", ".join(r['matched_evidence']) or "None")
                st.write("**Rules fired:**", ", ".join(r['fired_rules']) or "No compound rule; ranking came from weighted evidence.")
                for x in r['rule_explanations']: st.write("-",x)
                st.write("**Recommended actions:**")
                for a in r['actions']:
                    st.write(f"- {a['action']} — Cost: {a['cost']}, Downtime: {a['downtime']}. {a['details']}")
'''
(SRC/'app.py').write_text(app,encoding='utf-8')

requirements='''streamlit>=1.39\npandas>=2.0\npytest>=8.0\n'''
(ROOT/'requirements.txt').write_text(requirements,encoding='utf-8')

readme='''# Centrifugal Pump Fault Diagnosis Knowledge-Based System\n\n**Course:** CT-359 Knowledge Based System\n\nThis is a complete academic prototype that represents centrifugal-pump maintenance knowledge as weighted production rules and uses forward-chaining style evidence evaluation to rank likely faults.\n\n## Features\n- 14 fault classes and 22 symbolic symptoms\n- 16 maintenance actions with cost/downtime categories\n- 14 compound production rules\n- Numeric sensor-to-symbolic evidence conversion\n- Ranked multi-fault diagnosis with confidence/evidence score\n- Explanation trace (matched evidence + fired rules)\n- Safety, repair-cost, and downtime metadata\n- Synthetic diagnostic-case dataset and operational sensor log\n- Streamlit demonstration UI\n\n## Important academic note\nThe datasets in `data/diagnostic_cases.csv` and `data/operational_sensor_log.csv` are **synthetic, reproducible educational data**, not measurements from a real plant. They are generated from the project knowledge model for demonstration and testing. Prototype thresholds are not OEM safety limits.\n\n## Run\n```bash\npip install -r requirements.txt\nstreamlit run src/app.py\n```\n\n## Test\n```bash\npytest -q\n```\n\n## Knowledge files\n- `components.csv` — pump components\n- `faults.csv` — fault classes, safety, cost, downtime\n- `symptoms.csv` — symbolic observations\n- `symptom_fault_weights.csv` — fault/evidence relationships\n- `rules.json` — compound IF-THEN diagnostic rules\n- `maintenance_actions.csv` — recommended actions\n- `diagnostic_cases.csv` — 280 synthetic labeled cases\n- `operational_sensor_log.csv` — 255 five-minute synthetic operating records\n\n## Viva one-line explanation\n**The knowledge base stores what the system knows; the inference engine decides how to use that knowledge to infer faults from observed evidence.**\n'''
(ROOT/'README.md').write_text(readme,encoding='utf-8')

# test cases
unit = r'''import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from inference_engine import diagnose, diagnose_from_sensor

def top_fault(evidence):
    return diagnose(evidence,top_n=1)[0]["fault_id"]

def test_bearing_failure():
    assert top_fault({"vibration_high","bearing_temp_high","grinding_noise"}) == "F01"

def test_cavitation():
    assert top_fault({"crackling_noise","suction_pressure_low","pressure_fluctuation","flow_low"}) == "F02"

def test_dry_running():
    assert top_fault({"no_flow","prime_failure","rapid_temp_rise","seal_temp_high"}) == "F07"

def test_air_ingress():
    assert top_fault({"air_bubbles","flow_fluctuation","pressure_fluctuation"}) == "F12"

def test_sensor_derivation():
    sensor={"vibration_mm_s_rms":8.5,"bearing_temp_c":90,"motor_temp_c":65,"flow_percent_of_baseline":100,
    "discharge_pressure_bar":5,"suction_pressure_bar_abs":1.2,"motor_current_a":34,"seal_temp_c":60,
    "pressure_fluctuation_percent":2,"abnormal_noise":True,"prime_ok":True}
    (results,_), evidence=diagnose_from_sensor(sensor)
    assert results[0]["fault_id"] == "F01"
    assert "vibration_high" in evidence
'''
(TESTS/'test_inference.py').write_text(unit,encoding='utf-8')

# demo cases JSON
cases=[
{"name":"Bearing failure","manual_evidence":["vibration_high","bearing_temp_high","grinding_noise"]},
{"name":"Cavitation","manual_evidence":["crackling_noise","suction_pressure_low","pressure_fluctuation","flow_low"]},
{"name":"Dry running","manual_evidence":["no_flow","prime_failure","rapid_temp_rise","seal_temp_high"]},
{"name":"Air ingress","manual_evidence":["air_bubbles","flow_fluctuation","pressure_fluctuation","discharge_pressure_low"]},
{"name":"Discharge restriction","manual_evidence":["discharge_pressure_high","flow_low","rapid_temp_rise"]},
]
(DATA/'demo_cases.json').write_text(json.dumps(cases,indent=2),encoding='utf-8')

print('Project core generated.')
