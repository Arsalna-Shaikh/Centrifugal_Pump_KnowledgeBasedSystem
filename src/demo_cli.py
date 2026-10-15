from inference_engine import diagnose

CASES = {
    '1': ('Bearing failure', {'vibration_high','bearing_temp_high','grinding_noise'}),
    '2': ('Cavitation', {'crackling_noise','suction_pressure_low','pressure_fluctuation','flow_low'}),
    '3': ('Dry running', {'no_flow','prime_failure','rapid_temp_rise','seal_temp_high'}),
    '4': ('Air ingress', {'air_bubbles','flow_fluctuation','pressure_fluctuation','discharge_pressure_low'}),
}

print('Centrifugal Pump KBS - CLI Demo')
for k,(name,_) in CASES.items(): print(f'{k}. {name}')
choice=input('Choose case [1-4]: ').strip() or '1'
name,evidence=CASES.get(choice, CASES['1'])
results,trace=diagnose(evidence, top_n=3)
print('\nEvidence:', ', '.join(sorted(evidence)))
for i,r in enumerate(results,1):
    print(f"\n{i}. {r['fault']} | Evidence score: {r['confidence']}% | Safety: {r['safety_priority']}")
    print('   Matched:', ', '.join(r['matched_evidence']) or 'None')
    print('   Rules:', ', '.join(r['fired_rules']) or 'None')
    for a in r['actions']:
        print('   Action:', a['action'])
