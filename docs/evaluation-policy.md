# Evaluation Policy

The local gate uses at least 60 Chinese/English router cases and 20 deterministic output cases. Router precision must be at least `0.97`, recall at least `0.93`, output contract compliance exactly `100%`, and fabricated citations exactly `0`.

An exact skill/workflow/runnable match counts as a true positive. Every mismatch contributes one false positive and one false negative. Output cases use synthetic, file-backed fixtures without network services or real customer data.

Recorded fixtures and deterministic command runs are reproducibility evidence. Provider-backed model evidence, real-platform benchmarks, and human blind review remain `missing evidence` until independently collected. Pending blind pairs do not enter agreement metrics.

Run the external local integration with `python3 scripts/run_yao_meta_gates.py --meta-root ../yao-meta-skill`. CI has no machine-local meta checkout and runs `python3 scripts/run_yao_meta_gates.py --verify-existing`, which requires at least 53 green recorded commands, a current source digest, and portable report paths.
