import subprocess


def update_cloud_run_env():
    env_vars = {}
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    # Construct the --set-env-vars string
    env_pair_list = []
    for k, v in env_vars.items():
        if v:  # Only set if not empty
            env_pair_list.append(f"{k}={v}")

    env_pairs_str = ",".join(env_pair_list)

    cmd = [
        "gcloud",
        "run",
        "services",
        "update",
        "ecommerce-support-agent",
        f"--set-env-vars={env_pairs_str}",
        "--project=my-agentic-lab",
        "--region=us-central1",
    ]

    print("Running command:", " ".join(cmd[:5]) + " ...")
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    print("STDOUT:")
    print(result.stdout)
    print("STDERR:")
    print(result.stderr)

    if result.returncode == 0:
        print("Successfully updated environment variables on Cloud Run!")
    else:
        print("Failed to update environment variables on Cloud Run.")


if __name__ == "__main__":
    update_cloud_run_env()
