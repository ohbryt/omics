# One-command reproducible pipeline. Run:  snakemake -c4 --use-conda
# Stages: select (code-gated) -> record env -> DE per dataset -> meta -> checksums -> verify.
# `verify` is the terminal target; the run is "done" only if it exits 0 (STATUS=PASS).

import json, csv
configfile: "config.yaml"

def included_accessions(_=None):
    """Read accessions that passed the selection gate (available only after rule select)."""
    p = config["paths"]["dataset_audit"]
    try:
        with open(p, newline="") as f:
            return [r["accession"] for r in csv.DictReader(f) if r["decision"].upper() == "INCLUDE"]
    except FileNotFoundError:
        return []

rule all:
    input: "results/.verify_passed"

# ---- 1. code-gated dataset selection ----
rule select:
    output:
        audit=config["paths"]["dataset_audit"],
        quarantine=config["paths"]["quarantine"]
    conda: "environment.yml"
    shell:
        "python dataset_selection_gate.py && "
        "test -f {output.audit}"

# ---- 2. record the exact environment that ran ----
rule record_env:
    output: env=config["paths"]["env_lock"], used=config["paths"]["run_config_used"]
    conda: "environment.yml"
    shell:
        "conda list --explicit > {output.env} && "
        "python scripts/record_run_config.py"

# ---- 3. differential expression per included dataset ----
rule de:
    input: audit=config["paths"]["dataset_audit"]
    output: de="results/de/{acc}_de.csv", method="results/de/{acc}_method.json"
    conda: "environment.yml"
    shell:
        # dispatch by assay; both scripts write *_de.csv and *_method.json (records fdr_scope, collapse rule)
        "Rscript scripts/02_differential_expression.R {wildcards.acc}"

# ---- 4. cross-dataset random-effects meta of standardized effects (never vote-counting) ----
rule meta:
    input: lambda wc: expand("results/de/{acc}_de.csv", acc=included_accessions())
    output: config["paths"]["meta_out"]
    conda: "environment.yml"
    shell: "Rscript scripts/03_meta_analyze.R"

# ---- 5. checksums of all result tables ----
rule checksums:
    input: config["paths"]["meta_out"]
    output: config["paths"]["checksums"]
    conda: "environment.yml"
    shell: "python scripts/00_checksums.py write"

# ---- 6. verifier (terminal gate) ----
rule verify:
    input:
        audit=config["paths"]["dataset_audit"],
        env=config["paths"]["env_lock"],
        used=config["paths"]["run_config_used"],
        meta=config["paths"]["meta_out"],
        cks=config["paths"]["checksums"],
        de=lambda wc: expand("results/de/{acc}_de.csv", acc=included_accessions())
    output: touch("results/.verify_passed")
    conda: "environment.yml"
    shell: "python scripts/verify.py"   # exits non-zero on any violation -> Snakemake fails the run
