CREATE TABLE IF NOT EXISTS assignment_runs (
    run_id NUMBER AUTOINCREMENT PRIMARY KEY,
    method VARCHAR(50) NOT NULL,
    parameters VARIANT NOT NULL,
    executed_by VARCHAR(255) NOT NULL,
    execution_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS assignment_decisions (
    decision_id NUMBER AUTOINCREMENT PRIMARY KEY,
    run_id NUMBER NOT NULL,
    registro_id NUMBER NOT NULL,
    usuario_id NUMBER,
    score FLOAT,
    reasons VARIANT,
    candidates VARIANT,
    previous_decision_id NUMBER,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (run_id) REFERENCES assignment_runs(run_id)
);

CREATE TABLE IF NOT EXISTS assignment_prompts (
    prompt_id NUMBER AUTOINCREMENT PRIMARY KEY,
    run_id NUMBER NOT NULL,
    registro_id NUMBER,
    provider VARCHAR(100),
    model VARCHAR(150),
    prompt_text TEXT NOT NULL,
    response_text TEXT,
    request_payload VARIANT,
    response_payload VARIANT,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (run_id) REFERENCES assignment_runs(run_id)
);

CREATE TABLE IF NOT EXISTS assignment_overrides (
    override_id NUMBER AUTOINCREMENT PRIMARY KEY,
    registro_id NUMBER NOT NULL,
    previous_decision_id NUMBER,
    new_usuario_id NUMBER,
    reason TEXT NOT NULL,
    executed_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
