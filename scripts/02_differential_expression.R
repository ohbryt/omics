#!/usr/bin/env Rscript
# Differential expression for ONE dataset, with FIXED choices read from config.yaml.
# Writes results/de/<acc>_de.csv and results/de/<acc>_method.json (verify.py checks the latter).
# TEMPLATE: fill in the dataset-specific case/control grouping (must come from the audited metadata,
# never guessed). Microarray branch shown in full; rna-seq branch stubbed.

suppressPackageStartupMessages({ library(yaml); library(jsonlite) })
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: 02_differential_expression.R <ACCESSION>")
acc <- args[1]

cfg <- yaml::read_yaml("config.yaml")
set.seed(cfg$seed)
dir.create("results/de", recursive = TRUE, showWarnings = FALSE)
assay <- tolower(cfg$required_assay)

write_method <- function(extra = list()) {
  m <- c(list(accession = acc, assay = assay, fdr_method = cfg$fdr_method,
              fdr_scope = cfg$fdr_scope, fdr_threshold = cfg$fdr_threshold,
              normalization = cfg$normalization, probe_collapse_rule = cfg$probe_collapse_rule,
              r_version = as.character(getRversion()),
              limma_version = as.character(packageVersion("limma"))), extra)
  write_json(m, sprintf("results/de/%s_method.json", acc), auto_unbox = TRUE, pretty = TRUE)
}

# ---- group labels MUST come from the audited sample metadata, not from guesswork ----
# Provide a curated mapping per dataset (e.g., config/grouping/<acc>.csv with GSM,group in {case,control}).
group_file <- sprintf("config/grouping/%s.csv", acc)
if (!file.exists(group_file)) {
  stop(sprintf("STOP: missing curated group mapping %s. Define case/control from audited metadata; do not guess.", group_file))
}
grouping <- read.csv(group_file, stringsAsFactors = FALSE)  # columns: sample_id, group

if (assay == "microarray") {
  suppressPackageStartupMessages({ library(GEOquery); library(affy); library(limma) })
  # 1. fixed normalization (RMA). Download raw CEL where possible for true RMA; else use normalized matrix with documented caveat.
  #    eset <- affy::rma(affy::ReadAffy(...))            # raw CELs
  #    expr <- Biobase::exprs(eset)
  # 2. fixed probe->gene collapse (config$probe_collapse_rule, e.g. jetset best-probe) using a PINNED annotation pkg.
  #    expr_gene <- collapse_probes(expr, rule = cfg$probe_collapse_rule, annotation = "<pinned .db>")
  # 3. limma DE on case vs control from `grouping`
  #    design <- model.matrix(~ factor(grouping$group, levels=c("control","case")))
  #    fit <- eBayes(lmFit(expr_gene[, grouping$sample_id], design))
  #    tt  <- topTable(fit, coef=2, number=Inf, adjust.method=cfg$fdr_method)   # BH across ALL genes = genome-wide
  #    out <- data.frame(gene=rownames(tt), log2fc=tt$logFC, p=tt$P.Value, fdr=tt$adj.P.Val)
  #    write.csv(out, sprintf("results/de/%s_de.csv", acc), row.names=FALSE)
  write_method(list(note = "microarray RMA + fixed collapse + limma; fill in raw-CEL retrieval and pinned annotation"))
  stop("TEMPLATE: implement the 3 marked microarray steps, then remove this stop().")
} else if (assay == "rna-seq") {
  suppressPackageStartupMessages({ library(DESeq2) })
  # counts <- <pinned quantifier output for acc>
  # dds <- DESeqDataSetFromMatrix(counts[, grouping$sample_id], colData=data.frame(group=grouping$group), design=~group)
  # res <- as.data.frame(results(DESeq(dds)))   # padj = BH across all genes = genome-wide
  # out <- data.frame(gene=rownames(res), log2fc=res$log2FoldChange, p=res$pvalue, fdr=res$padj)
  # write.csv(out, sprintf("results/de/%s_de.csv", acc), row.names=FALSE)
  write_method(list(deseq2_version = as.character(packageVersion("DESeq2"))))
  stop("TEMPLATE: wire in the pinned RNA-seq quantification, then remove this stop().")
} else {
  stop(sprintf("unknown assay in config: %s", assay))
}
