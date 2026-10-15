import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from inference_engine import diagnose, diagnose_from_sensor

def top_fault(evidence):
    return diagnose(evidence,top_n=1)[0][0]["fault_id"]

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
