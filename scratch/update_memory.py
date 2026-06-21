import subprocess


def update_memory():
    cmd = [
        "gcloud",
        "run",
        "services",
        "update",
        "ecommerce-support-agent",
        "--memory=4Gi",
        "--project=my-agentic-lab",
        "--region=us-central1",
    ]
    print("Running command:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)

    if result.returncode == 0:
        print("Successfully updated memory to 4Gi on Cloud Run!")
    else:
        print("Failed to update memory on Cloud Run.")


if __name__ == "__main__":
    update_memory()
