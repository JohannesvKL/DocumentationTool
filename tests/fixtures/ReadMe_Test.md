# Minimal Nextflow DSL2 Pipeline

This is a simple [Nextflow](https://www.nextflow.io/) DSL2 pipeline demonstrating:
- how to use parameters,
- how to pass them to processes,
- and how to print a final message when the workflow finishes (success or failure).

---

## What the pipeline does

- Accepts two parameters:
  - `--message` — a text string to print.  
  - `--count` — how many times to print it.  
- Runs a single process (`sayHello`) that:
  1. Prints the message.
  2. Prints it repeatedly the specified number of times.
- Prints **"Workflow complete!"** if everything succeeds, or an error message if it fails.

---

## Files

- `main.nf` — main Nextflow pipeline script.  
- *(optional)* `nextflow.config` — can be used to set default parameter values.

---

## Usage

### 1. Install Nextflow (if you haven’t)
```bash
curl -s https://get.nextflow.io | bash
mv nextflow ~/bin/    # or anywhere in your PATH
