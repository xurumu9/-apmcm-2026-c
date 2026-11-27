"""Two-stage structural and weighted classifier; exploratory validation only."""
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import platform

import numpy as np
import scipy
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/raw/acoustics/Data01_AfricanPenguins_seasurface_calls_acoustics.csv"
OUT = ROOT / "results/q1"
FEATURES = ("Duration", "F01", "Fpeak", "Q25", "Q50", "Q75")
LABELS = ("flat", "mod", "tv")
SEEDS = (1, 2, 3, 4, 42)


def missing(value):
    return value.strip().lower() in {"", "na", "nan", "null"}


def load_data():
    with INPUT.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"Date", "CallType", "F02", "PulseRate", *FEATURES}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Required columns missing")
        rows = list(reader)
    x, y, groups, f02, pulse = [], [], [], [], []
    for line, row in enumerate(rows, 2):
        label = row["CallType"].strip().lower()
        if label not in LABELS or not row["Date"].strip():
            raise ValueError(f"Invalid call type or date at line {line}")
        numeric = [float(row[name]) for name in FEATURES]
        if not all(np.isfinite(numeric)):
            raise ValueError(f"Missing or non-finite common feature at line {line}")
        for name in ("F02", "PulseRate"):
            if not missing(row[name]) and not np.isfinite(float(row[name])):
                raise ValueError(f"Non-finite {name} at line {line}")
        has_pulse = not missing(row["PulseRate"])
        x.append(numeric + [float(row["PulseRate"]) if has_pulse else np.nan, int(has_pulse)])
        y.append(label)
        groups.append(row["Date"].strip())
        f02.append(not missing(row["F02"]))
        pulse.append(has_pulse)
    return np.asarray(x), np.asarray(y), np.asarray(groups), np.asarray(f02), np.asarray(pulse)


def classifier():
    preprocessing = ColumnTransformer([
        ("common", StandardScaler(), list(range(6))),
        ("pulse", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), [6]),
        ("pulse_present", "passthrough", [7]),
    ])
    return make_pipeline(preprocessing, LogisticRegression(C=1.0, max_iter=3000, random_state=42))


def metric_summary(actual, predicted):
    return dict(accuracy=accuracy_score(actual, predicted),
                balanced_accuracy=balanced_accuracy_score(actual, predicted),
                macro_f1=f1_score(actual, predicted, average="macro", zero_division=0),
                confusion_matrix=confusion_matrix(actual, predicted, labels=LABELS).tolist())


def cross_validate(x, y, f02, splits):
    predictions = np.empty(len(y), dtype="<U4")
    for train, test in splits:
        predictions[test[f02[test]]] = "tv"
        train_non_tv = train[~f02[train]]
        test_non_tv = test[~f02[test]]
        if len(test_non_tv) == 0:
            continue
        if set(y[train_non_tv]) != {"flat", "mod"}:
            raise ValueError("Training fold lacks flat or mod; structural input may not be applicable")
        fitted = classifier().fit(x[train_non_tv], y[train_non_tv])
        predictions[test_non_tv] = fitted.predict(x[test_non_tv])
    return predictions


def main():
    x, y, groups, f02, pulse = load_data()
    if set(y[~f02]) != {"flat", "mod"}:
        raise ValueError("Non-F02 records do not match the binary training task")
    date_pred = cross_validate(x, y, f02, LeaveOneGroupOut().split(x, y, groups))
    random_results = []
    for seed in SEEDS:
        splits = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed).split(x, y)
        random_results.append(dict(seed=seed, **metric_summary(y, cross_validate(x, y, f02, splits))))
    baseline = np.where(f02, "tv", np.where(pulse, "mod", "flat"))
    fit = classifier().fit(x[~f02], y[~f02])
    transform = fit.named_steps["columntransformer"]
    common = transform.named_transformers_["common"]
    pulse_pipe = transform.named_transformers_["pulse"]
    linear = fit.named_steps["logisticregression"]
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    n_mod_missing = int(np.sum((y == "mod") & ~f02 & ~pulse))
    result = dict(
        run_id=datetime.now(timezone.utc).strftime("q1_weighted_%Y%m%dT%H%M%SZ"),
        input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        git_head=head, code_state="See script_sha256; working tree may differ from HEAD.",
        features=list(FEATURES) + ["PulseRate", "pulse_observed"], label_order=list(LABELS),
        model="F02-recorded -> tv; otherwise logistic regression, C=1, 0.5 threshold",
        preprocessing="Six predictors standardized; pulse median imputed and standardized within training fold; pulse-observed indicator unscaled.",
        structural_rule_in_sample=metric_summary(y, baseline),
        leave_one_date_out=metric_summary(y, date_pred),
        random_stratified_5fold=random_results,
        missing_pulse_mod_n=n_mod_missing,
        missing_pulse_mod_correct=int(np.sum((y == "mod") & ~f02 & ~pulse & (date_pred == "mod"))),
        full_data_fit=dict(positive_class=linear.classes_[1], intercept=float(linear.intercept_[0]),
                           coefficients=linear.coef_[0].tolist(),
                           common_means=common.mean_.tolist(), common_scales=common.scale_.tolist(),
                           pulse_imputed_median=pulse_pipe.named_steps["simpleimputer"].statistics_.tolist(),
                           pulse_mean=pulse_pipe.named_steps["standardscaler"].mean_.tolist(),
                           pulse_scale=pulse_pipe.named_steps["standardscaler"].scale_.tolist()),
        validation_limit="F02 recording status reflects category/measurement process; not independently tested on unknown recordings. Date is not individual ID. Models explored on this dataset.",
        versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, sklearn=sklearn.__version__))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "weighted_classifier_metadata.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
