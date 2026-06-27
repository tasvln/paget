# Multi-Agent Code Generation

A lightweight multi-agent framework for orchestrating multiple LLM-powered agents to collaboratively generate software from a structured project specification.

Rather than asking a single language model to generate an entire application, this framework decomposes a project into independent components, distributes them across specialist agents, coordinates execution, validates generated artifacts, and manages automatic refinement when generation fails.

> **Status:** Experimental research project.

<img width="797" height="416" alt="Screenshot 2026-06-26 203642" src="https://github.com/user-attachments/assets/f48d7884-c42b-4448-a12b-595112fcb2df" />

<img width="792" height="463" alt="Screenshot 2026-06-26 203811" src="https://github.com/user-attachments/assets/dd90b225-3c2b-44d7-b1aa-e651ba4b89d6" />

<img width="392" height="153" alt="Screenshot 2026-06-26 203831" src="https://github.com/user-attachments/assets/623d9ef0-b028-41f7-88c9-598ec49dfa33" />

---

# Features

* Manager agent reads a project specification (`SPEC.json`)
* Automatic decomposition into implementation tasks
* Central coordinator responsible for scheduling and orchestration
* Multiple specialist agents generating code concurrently
* Persistent shared state between agents
* Dependency-aware task scheduling
* Automatic refinement retries for failed generations
* Optional validation agent
* Artifact-based output generation

---

# Architecture

```
                  SPEC.json
                      │
                      ▼
              Manager Agent
                      │
                      ▼
               Coordinator API
                      │
     ┌────────────────┴────────────────┐
     ▼                                 ▼
Specialist Agent 1              Specialist Agent 2
     │                                 │
     ▼                                 ▼
Generated Artifacts             Generated Artifacts
     │                                 │
     └────────────────┬────────────────┘
                      ▼
              Validator Agent
                      │
                      ▼
              Retry / Completion
```

The coordinator is the central authority.

Agents never communicate directly with each other.

All communication happens through the coordinator's REST API and the shared project state.

---

# Components

## Manager Agent

Responsible for:

* Reading `SPEC.json`
* Creating implementation tasks
* Creating validation tasks
* Registering the project
* Monitoring project progress

The manager performs project decomposition once and then becomes read-only.

---

## Coordinator

The coordinator is responsible for:

* Agent registration
* Task scheduling
* Dependency resolution
* Shared state management
* Retry management
* Refinement creation
* Unlocking dependent tasks

The coordinator is the single source of truth for the entire project.

---

## Specialist Agent

Each specialist agent:

* Requests an available implementation task
* Generates source code using a local LLM
* Performs basic syntax validation
* Saves generated artifacts
* Reports completion back to the coordinator

Specialists never communicate with each other.

---

## Validator Agent (Optional)

The validator performs an independent verification pass.

It currently checks:

* Generated file exists
* Python syntax is valid
* Module executes successfully
* Optional user-written tests

Validation failures trigger automatic refinement through the coordinator.

---

# Project Structure

```
project/
│
├── agents/
│   ├── manager.py
│   ├── specialist.py
│   └── validator.py
│
├── coordinator/
│   ├── server.py
│   ├── models.py
│
├── shared/
│   └── manager_state.py
│
├── spec/
│   └── spec.json
│ 
├── output/
│   ├── *.py files
│   └── main.py

```

---

# Workflow

1. Start the coordinator.

2. Launch the manager.

3. The manager loads `SPEC.json`.

4. Tasks are created.

5. Specialist agents request work.

6. Generated artifacts are written to `output/`.

7. Validation tasks execute.

8. Failed validation creates refinement tasks.

9. Successful validation completes the project.

---

# Example Specification

```json
{
  "project": "calculator",

  "components": [
    {
      "name": "adder",
      "description": "add two numbers",
      "requirements": [
        "create add(a,b)"
      ]
    },
    {
      "name": "multiplier",
      "description": "multiply two numbers",
      "requirements": [
        "create multiply(a,b)"
      ]
    }
  ]
}
```

---

# Generated Output

```
output/

calculator-adder.py
calculator-multiplier.py
main.py
```

Each component is generated independently as its own artifact.

If validation succeeds for every component, a simple `main.py` entry point is generated automatically.

---

# Shared State

All coordination is persisted in:

```
shared/manager_state.json
```

The shared state tracks:

* Registered agents
* Task queue
* Task status
* Dependencies
* Validation errors
* Retry counts
* Timing information

This allows every agent to remain stateless.

---

# Running

Start the coordinator:

```bash
python coordinator.py
```

Start the manager:

```bash
python manager.py spec.json
```

Start one or more specialists:

```bash
python specialist.py agent-1
python specialist.py agent-2
python specialist.py agent-3
```

(Optional)

Start the validator:

```bash
python validator.py
```

---

# Current Limitations

This project is intended as an experimental orchestration framework rather than a production code generation system.

Current limitations include:

* Generated code quality depends heavily on the selected LLM.
* Components are generated independently without semantic integration.
* Validation currently focuses on syntax and executable modules.
* Generated `main.py` only imports validated components.
* The specification format is intentionally minimal.

---

# Future Work

Potential improvements include:

* Semantic validation of generated code
* Automatic unit test generation
* Cross-component dependency analysis
* Language-agnostic code generation
* Build system generation
* Docker project scaffolding
* Artifact versioning
* Smarter task scheduling and prioritization
* Distributed execution across multiple machines

---

# Dependencies

* Python
* FastAPI
* Pydantic
* OpenAI-compatible local inference server
* REST API
* JSON project specifications

---

# Research Goal

The objective of this project is to investigate whether a distributed multi-agent architecture can improve software generation by separating responsibilities across specialized agents coordinated through a centralized scheduler.

Instead of relying on a single LLM prompt to generate an entire application, the framework explores task decomposition, concurrent generation, independent validation, and iterative refinement as mechanisms for scalable software synthesis.
