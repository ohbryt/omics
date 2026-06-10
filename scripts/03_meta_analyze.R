#!/usr/bin/env Rscript
# Cross-dataset combination by RANDOM-EFFECTS META-ANALYSIS of standardized effects.
# NEVER vote-counting ("X up / Y down"). Reads results/de/*_de.csv, requires each to carry a
# standardized effect (or SE) per gene; pools per gene across datasets and reports I^2.

suppressPackageStartupMessages({ library(yaml); library(metafor) })
cfg <- yaml::read_yaml("config.yaml"); set.seed(cfg$seed)

de_files <- list.files("results/de", pattern="_de\\.csv$", full.names=TRUE)
if (length(de_files) == 0) stop("no DE result files found")

# Expect columns: gene, log2fc, se   (compute/standardize SE upstream in 02_*.R; do not impute)
load_one <- function(f) {
  d <- read.csv(f, stringsAsFactors=FALSE)
  if (!all(c("gene","log2fc") %in% names(d))) stop(paste("missing gene/log2fc in", f))
  if (!"se" %in% names(d)) stop(paste("missing 'se' (standardized effect SE) in", f,
                                      "- compute it in 02_differential_expression.R; SEs are not imputed."))
  d$dataset <- sub("_de\\.csv$","", basename(f)); d
}
dat <- do.call(rbind, lapply(de_files, load_one))

min_k <- 3L  # pool a gene only if present in >= 3 datasets (match the atlas Tier-A rule)
genes <- names(which(table(dat$gene) >= min_k))

res <- lapply(genes, function(g) {
  s <- dat[dat$gene == g, ]
  m <- tryCatch(rma(yi = s$log2fc, sei = s$se, method = "REML"), error = function(e) NULL)
  if (is.null(m)) return(NULL)
  data.frame(gene=g, k=nrow(s), pooled_log2fc=as.numeric(m$b), se=m$se,
             ci_lb=m$ci.lb, ci_ub=m$ci.ub, p=m$pval, I2=m$I2)
})
res <- do.call(rbind, Filter(Negate(is.null), res))
res$fdr <- p.adjust(res$p, method = cfg$fdr_method)   # genome-wide across pooled genes
res <- res[order(res$fdr), ]
write.csv(res, cfg$paths$meta_out, row.names = FALSE)
cat(sprintf("meta: pooled %d genes (k>=%d) across %d datasets -> %s\n",
            nrow(res), min_k, length(de_files), cfg$paths$meta_out))
