"""Reproduce Q4 illustrative scores from version-pinned, aggregated Q2/Q3 outputs."""
import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/q4"
Q2 = ("6306e8e", "experiments/reports/q2_2_descriptive_summary.csv")
Q3 = ("9a7e06f", "experiments/reports/q3_release/q4_combination_original_flags_36.csv")
CALLS = ("flat", "mod", "tv")
DISTANCES = (4, 8, 16, 32, 64, 128, 256)
WEIGHTS = {"equal": (1/3, 1/3, 1/3), "head_focus": (.6, .2, .2),
           "vocal_focus": (.2, .6, .2), "approach_focus": (.2, .2, .6)}


def source(ref):
    data = subprocess.check_output(["git", "show", f"{ref[0]}:{ref[1]}"], cwd=ROOT)
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig")))), hashlib.sha256(data).hexdigest()


def nonincreasing(values):
    blocks = []
    for i, val in enumerate(values):
        blocks.append([i, i, val, 1])
        while len(blocks) > 1 and blocks[-2][2] < blocks[-1][2]:
            a, b = blocks[-2:]
            count = a[3] + b[3]
            blocks[-2:] = [[a[0], b[1], (a[2]*a[3]+b[2]*b[3])/count, count]]
    result = [0.0] * len(values)
    for start, end, value, _ in blocks:
        for i in range(start, end + 1):
            result[i] = value
    return result


def interpolate(nodes, distance):
    for i in range(len(DISTANCES)-1):
        a, b = DISTANCES[i:i+2]
        if a <= distance <= b:
            return nodes[i] + (nodes[i+1]-nodes[i])*(distance-a)/(b-a)
    raise ValueError("distance outside Q2 domain")


def main():
    q2, h2 = source(Q2)
    q3, h3 = source(Q3)
    curves = {}
    for call in CALLS:
        means = []
        for distance in DISTANCES:
            r = [x for x in q2 if x["call_type"] == call and int(x["distance_m"]) == distance]
            assert len(r) == 3 and {x["metric"] for x in r} == {"spectrogram", "amplitude_spectrum", "envelope"}
            means.append(sum(float(x["mean"]) for x in r)/3)
        curves[call] = nonincreasing(means)
    groups = {}
    for x in q3:
        if x["resampling_unit"] != "expID" or x["call_type"] not in CALLS:
            continue
        key = (x["call_type"], x["context"], int(x["distance_m"]))
        assert x["n_penguins"] == "8" and x["vocal_ncalls_before"] == "0"
        groups.setdefault(key, []).append(x)
    assert len(groups) == 27
    out = []
    for (call, context, distance), rows in sorted(groups.items()):
        assert len(rows) == 8 and {x["combo"] for x in rows} == {f"{n:03b}" for n in range(8)}
        prob = {x["combo"]: float(x["probability"]) for x in rows}
        assert all(0 <= p <= 1 for p in prob.values()) and abs(sum(prob.values())-1) < 1e-8
        support = {x["joint_support"] for x in rows}
        assert len(support) == 1
        marginals = [sum(v for state, v in prob.items() if state[j] == "1") for j in range(3)]
        p_any = 1-prob["000"]
        fidelity = interpolate(curves[call], distance)
        for weight_name, w in WEIGHTS.items():
            raw_score = sum(a*b for a,b in zip(w,marginals))
            for threshold in (.5,.6,.7):
                for reduction in (0,.05,.10,.15,.20):
                    eligible = (1-reduction)*fidelity >= threshold
                    for fraction in (.25,.5,.75):
                        out.append({"call_type":call,"context":context,"distance_m":distance,
                          "n_penguins":8,"joint_support":next(iter(support)),
                          "q2_fidelity":fidelity,"threshold":threshold,"reduction":reduction,
                          "weight_scenario":weight_name,"w_head":w[0],"w_vocal":w[1],"w_approach":w[2],
                          "p_head":marginals[0],"p_vocal_increase":marginals[1],"p_approach":marginals[2],
                          "p_any_original_marker":p_any,"raw_behavior_score":raw_score,
                          "meets_fidelity_scenario":int(eligible),"scenario_score":raw_score*eligible,
                          "fraction_given_any":fraction,"scenario_expected_responder_count":8*p_any*fraction*eligible})
    assert len(out)==27*4*3*5*3
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT/"scenario_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(out[0])); writer.writeheader(); writer.writerows(out)
    meta={"q2_commit":Q2[0],"q2_path":Q2[1],"q2_sha256":h2,"q3_commit":Q3[0],"q3_path":Q3[1],"q3_sha256":h3,
          "rows":len(out),"randomness":False,"population":"N=8, baseline vocal count=0",
          "limitations":"scenario scores and assumed counts, not observed response probabilities under noise; no confidence intervals"}
    (OUT/"scenario_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
