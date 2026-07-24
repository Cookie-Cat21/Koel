# W5 ≤2k on material_median fpv2+liq_v4

nested_contract_met: `False`

## Hyper winners

[
  {
    "fingerprint": "lgb_ea81dc230e",
    "config": {
      "learning_rate": 0.02,
      "max_depth": 8,
      "num_leaves": 95,
      "subsample": 0.7,
      "colsample_bytree": 0.75,
      "reg_lambda": 100.0
    },
    "calibration": {
      "rank_ic": 0.26503763017337995,
      "balanced_accuracy": 0.5930424725343582,
      "mcc": 0.18670748982981517,
      "n_rows": 2478,
      "n_sessions": 37,
      "spread_112": -0.009661703506548599,
      "spread_30": 0.020563264318419226
    },
    "test": {
      "rank_ic": 0.3042805903151278,
      "balanced_accuracy": 0.6097242649971693,
      "mcc": 0.21942366565719434,
      "n_rows": 2896,
      "n_sessions": 39,
      "spread_112": 0.0011640466291386188,
      "spread_30": 0.03074261805771005
    },
    "beats_baseline": true
  },
  {
    "fingerprint": "lgb_c86ec66a2b",
    "config": {
      "learning_rate": 0.02,
      "max_depth": 8,
      "num_leaves": 63,
      "subsample": 0.7,
      "colsample_bytree": 0.75,
      "reg_lambda": 100.0
    },
    "calibration": {
      "rank_ic": 0.2646062160387027,
      "balanced_accuracy": 0.5946598646560006,
      "mcc": 0.18995309600167262,
      "n_rows": 2478,
      "n_sessions": 37,
      "spread_112": -0.009663311485474625,
      "spread_30": 0.020614423392260252
    },
    "test": {
      "rank_ic": 0.30353006669282373,
      "balanced_accuracy": 0.6074431596370399,
      "mcc": 0.2146515983549111,
      "n_rows": 2896,
      "n_sessions": 39,
      "spread_112": -0.00012862926499021784,
      "spread_30": 0.029682726046365095
    },
    "beats_baseline": true
  },
  {
    "fingerprint": "lgb_03716bf22e",
    "config": {
      "learning_rate": 0.02,
      "max_depth": 8,
      "num_leaves": 127,
      "subsample": 0.7,
      "colsample_bytree": 0.75,
      "reg_lambda": 100.0
    },
    "calibration": {
      "rank_ic": 0.26329354211128503,
      "balanced_accuracy": 0.5927637693721542,
      "mcc": 0.18624976066962876,
      "n_rows": 2478,
      "n_sessions": 37,
      "spread_112": -0.00785272661805413,
      "spread_30": 0.022224493459165946
    },
    "test": {
      "rank_ic": 0.3056556792459733,
      "balanced_accuracy": 0.61178640729147,
      "mcc": 0.2233934782223139,
      "n_rows": 2896,
      "n_sessions": 39,
      "spread_112": 0.0008951222212851138,
      "spread_30": 0.030428638704801596
    },
    "beats_baseline": true
  }
]
