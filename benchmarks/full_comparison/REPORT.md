# Full S-Lang / Python / C++ comparison

Descriptive comparison; no overall score or winner is assigned.
Result: 14/14 tasks produce matching outputs across S-Lang, Python, and C++.

| Case | S-Lang LOC | Python LOC | C++ LOC | Match | S-Lang interpreter (s) | Python (s) | C++ (s) | Native match |
|---|---:|---:|---:|:---:|---:|---:|---:|:---:|
| pipeline | 8 | 5 | 9 | yes | 0.8337 | 0.6720 | 0.0019 | skipped |
| reduce | 3 | 3 | 5 | yes | 0.8501 | 0.7211 | 0.0018 | skipped |
| sequence | 3 | 6 | 9 | yes | 0.9173 | 0.7485 | 0.0017 | skipped |
| entity | 8 | 10 | 8 | yes | 0.8400 | 0.6431 | 0.0019 | skipped |
| physics | 9 | 9 | 12 | yes | 0.8182 | 0.6538 | 0.0022 | skipped |
| filter-sort | 8 | 3 | 10 | yes | 0.7982 | 0.6587 | 0.0023 | skipped |
| circle | 4 | 4 | 6 | yes | 0.8574 | 0.6303 | 0.0017 | skipped |
| csv_analysis | 4 | 8 | 8 | yes | 0.8772 | 0.7056 | 0.0018 | yes |
| json_processing | 4 | 6 | 4 | yes | 0.8460 | 0.6422 | 0.0016 | yes |
| text_processing | 5 | 8 | 8 | yes | 0.9071 | 0.6692 | 0.0016 | yes |
| statistics | 6 | 6 | 12 | yes | 0.7964 | 0.6481 | 0.0019 | yes |
| file_roundtrip | 6 | 9 | 9 | yes | 0.9117 | 0.6861 | 0.0018 | yes |
| log_analysis | 4 | 5 | 5 | yes | 0.9091 | 0.6904 | 0.0017 | yes |
| config_processing | 6 | 6 | 9 | yes | 0.9224 | 0.6734 | 0.0017 | yes |

Total corpus source lines: S-Lang 78, Python 88, C++ 114.

Timing note: measurements include process startup. C++ compilation is excluded from runtime; S-Lang native timing includes its current native invocation, so these numbers are not a pure backend benchmark.

Infrastructure note: the control and real-world corpora run in isolated child processes.
Native execution note: native checks were skipped for this refreshed LOC-focused report; no native-backend conclusion is drawn.
