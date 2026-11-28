| model                          |       size |     params | backend    | ngl | n_ubatch | type_k | type_v |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -------: | -----: | -----: | --: | --------------: | -------------------: |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 |          pp2048 |       1213.90 ± 1.14 |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 |           tg256 |         80.43 ± 0.09 |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 | pp2048 @ d32768 |        591.47 ± 0.84 |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 |  tg256 @ d32768 |         71.67 ± 0.27 |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 | pp2048 @ d131072 |        234.21 ± 0.09 |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 | tg256 @ d131072 |         55.33 ± 0.14 |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 | pp2048 @ d196608 |        166.11 ± 0.10 |
| inkling2_loop ?B IQ3_S - 3.4375 bpw |  10.63 GiB |    26.07 B | CUDA       | 999 |       64 |   q8_0 |   q8_0 |   1 | tg256 @ d196608 |         48.21 ± 0.08 |

build: af5c58347 (12679)
