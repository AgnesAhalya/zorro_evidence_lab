# Data sources

The pilot uses local, pinned copies of both public sources.

| Source | Local path | Revision | License |
|---|---|---|---|
| MuSR murder cases | `vendor/musr/murder_mystery.csv` | `7c365b439a222150f317764d4f16ae6c96d7d94a3` | CC BY 4.0 |
| NarraCrime-300 | `vendor/evar/dataset/` | `3f48324fde2bc332d48e3a61608a90fd2a4e7923` | CC BY 4.0 |

The loaders preserve source narratives unchanged. Ground truth and NarraCrime evidence annotations are kept in the private controller manifest and are never included in ordinary target-model prompts.

Source repositories:

- https://huggingface.co/datasets/TAUR-Lab/MuSR
- https://github.com/Cosinecos/EVAR
