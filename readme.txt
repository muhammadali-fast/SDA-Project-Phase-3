====================================================================
  Generic Concurrent Real-Time Data Processing Pipeline
  Phase 3 – SDA Spring 2026
====================================================================

QUICK START
-----------
1. Place your dataset CSV inside:    project/data/
2. Edit config.json to point to it:  "dataset_path": "data/<your_file>.csv"
3. Update config.json schema_mapping so source_name values match your CSV headers.
4. Run:
       cd project/
       python main.py

Requirements: Python 3.10+, matplotlib
Install deps: pip install matplotlib


MAIN FILE
---------
  project/main.py  ← this is the ONLY file you run


FOLDER STRUCTURE
----------------
project/
│
├── main.py                     ← Central Orchestrator (DIP injection point)
├── config.json                 ← ONLY file that changes between datasets
├── readme.txt                  ← This file
│
├── data/
│   └── sample_sensor_data.csv  ← Replace with your dataset
│
├── input_module/
│   ├── __init__.py
│   └── csv_reader.py           ← CSVInputModule: reads CSV, maps schema, pushes to raw_queue
│
├── core_module/
│   ├── __init__.py
│   ├── functional_core.py      ← Pure functions: verify_packet, compute_running_average
│   ├── worker.py               ← CoreWorker: stateless, runs in N parallel processes
│   └── aggregator.py           ← Aggregator: stateful sliding-window, single process
│
├── output_module/
│   ├── __init__.py
│   └── dashboard.py            ← Dashboard: matplotlib real-time charts + telemetry bars
│
├── telemetry/
│   ├── __init__.py
│   └── pipeline_telemetry.py   ← PipelineTelemetry: Observer Subject, polls queue sizes
│
└── utils/
    ├── __init__.py
    ├── interfaces.py            ← ALL abstract classes / interfaces (DIP contracts)
    └── config_loader.py        ← Typed config.json accessor


CONFIG.JSON EXPLAINED
---------------------
{
  "dataset_path": "data/sample_sensor_data.csv",
    → Path to your CSV, relative to project root.

  "pipeline_dynamics": {
    "input_delay_seconds": 0.05,
      → Pause between rows to simulate a live stream.
        Set to 0.0 for maximum speed.
    "core_parallelism": 4,
      → Number of CoreWorker processes.
    "stream_queue_max_size": 50
      → Max items in each multiprocessing.Queue.
        When full, input automatically blocks (back-pressure).
  },

  "schema_mapping": {
    "columns": [
      { "source_name": "Sensor_ID",      "internal_mapping": "entity_name",  "data_type": "string"  },
      { "source_name": "Timestamp",      "internal_mapping": "time_period",  "data_type": "integer" },
      { "source_name": "Raw_Value",      "internal_mapping": "metric_value", "data_type": "float"   },
      { "source_name": "Auth_Signature", "internal_mapping": "security_hash","data_type": "string"  }
    ]
  },
    → Map YOUR CSV column names to the four internal fields.
      internal_mapping values must always be:
        entity_name, time_period, metric_value, security_hash
      data_type: "string" | "integer" | "float"

  "processing": {
    "stateless_tasks": {
      "operation":   "verify_signature",
      "algorithm":   "pbkdf2_hmac",
      "iterations":  100000,
      "secret_key":  "sda_spring_2026_secure_key"
    },
    "stateful_tasks": {
      "operation":               "running_average",
      "running_average_window_size": 10
    }
  },

  "visualizations": {
    "telemetry": {
      "show_raw_stream":          true,
      "show_intermediate_stream": true,
      "show_processed_stream":    true
    },
    "data_charts": [
      { "type": "real_time_line_graph_values",  "title": "...", "x_axis": "time_period", "y_axis": "metric_value"    },
      { "type": "real_time_line_graph_average", "title": "...", "x_axis": "time_period", "y_axis": "computed_metric" }
    ]
  }
}


TESTING WITH AN UNSEEN DATASET
-------------------------------
Step 1 – Prepare your dataset CSV.
  The CSV must have exactly 4 columns:
    a) An entity identifier (e.g. sensor name, country, city …)
    b) A numeric time field (epoch seconds, row index, year …)
    c) A numeric measurement value (float)
    d) A pre-computed PBKDF2-HMAC-SHA256 auth signature

  The signature is computed as:
    password = secret_key  (from config)
    salt     = str(round(metric_value, 2))
    hash     = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations)
    signature = hash.hex()

Step 2 – Place the CSV in project/data/.

Step 3 – Edit ONLY config.json:
  a) Change "dataset_path"  to  "data/<your_file>.csv"
  b) Change "schema_mapping.columns[*].source_name" to your actual CSV headers.
  c) Optionally adjust pipeline_dynamics and processing parameters.

Step 4 – Run:    python main.py
  No Python source code modification is needed.


DESIGN PRINCIPLES SUMMARY
--------------------------
Dependency Inversion Principle
  All modules depend on abstract interfaces in utils/interfaces.py.
  main.py is the only place where concrete classes are imported.

Single Responsibility Principle
  Each class has exactly one reason to change:
    CSVInputModule   → reading and mapping CSV rows
    CoreWorker       → stateless packet authentication
    Aggregator       → stateful sliding-window computation
    Dashboard        → visual rendering
    PipelineTelemetry→ queue-health monitoring

Open/Closed Principle
  Adding a new data source: implement AbstractInputModule, register in main.py.
  Adding a new chart type:  add a case in dashboard.py's _animate method.
  No existing code is modified.

Observer Pattern
  PipelineTelemetry (Subject) → notifies → Dashboard (Observer)
  The Subject never imports the Dashboard; it knows only TelemetryObserver.

Producer-Consumer Pattern
  Input  → raw_queue       → CoreWorkers (parallel)
  Core   → verified_queue  → Aggregator  (single)
  Aggregator → processed_queue → Dashboard

Functional Core / Imperative Shell
  Pure functions (verify_packet, compute_running_average) in functional_core.py
  have NO side effects and are safe to call from any process.
  CoreWorker and Aggregator are the imperative shells that manage I/O and state.


CONCURRENCY MODEL
-----------------
Process                Role                         Queue I/O
------------------------------------------------------------------
Input-CSV              Stream rows from CSV         PUT  → raw_queue
Core-Worker-1..N       Parallel authentication      GET  raw_queue   PUT → verified_queue
Core-Aggregator        Sliding-window average       GET  verified_q  PUT → processed_queue
Output-Dashboard       Render charts                GET  processed_q
[Daemon thread]        Telemetry polling            POLL raw_q & processed_q

Back-pressure:
  raw_queue and processed_queue are bounded (stream_queue_max_size).
  multiprocessing.Queue.put() blocks automatically when full,
  throttling the producer without any extra code.

Shutdown (poison-pill pattern):
  Input sends N sentinels (None) to raw_queue  (one per CoreWorker).
  Each CoreWorker, on receiving None, sends one None to verified_queue and exits.
  Aggregator counts N Nones from verified_queue, then sends one None to processed_queue.
  Dashboard receives None and marks the pipeline complete.


TROUBLESHOOTING
---------------
"Dataset not found"
  → Check dataset_path in config.json is correct relative to project root.

"Column X not found in CSV row"
  → Check schema_mapping.columns[*].source_name matches your CSV headers exactly.

"Cast failed for column X"
  → The value in that column cannot be converted to the configured data_type.

Dashboard window does not open
  → Ensure a display is available (not headless SSH without X forwarding).
  → Try changing matplotlib.use("TkAgg") in dashboard.py to "Qt5Agg" or "Agg".

Slow performance
  → Reduce hash_iterations in config (default 100 000 is intentionally heavy).
  → Increase core_parallelism.
  → Reduce input_delay_seconds to 0.

