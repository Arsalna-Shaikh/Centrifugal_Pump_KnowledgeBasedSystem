import streamlit as st
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
