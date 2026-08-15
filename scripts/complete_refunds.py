import os
from datetime import datetime, timedelta

from tools.db import get_connection


def complete_old_refunds():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Find pending refunds older than 2 days
                cutoff = datetime.now() - timedelta(days=2)

                cur.execute(
                    """
                    UPDATE refunds
                    SET status = 'completed'
                    WHERE status = 'pending' AND updated_at <= %s
                """,
                    (cutoff,),
                )

                updated_rows = cur.rowcount
                conn.commit()
                print(f"Successfully marked {updated_rows} old pending refunds as completed.")
    except Exception as e:
        print(f"Error updating refunds: {e}")


if __name__ == "__main__":
    import yaml

    # Load from env.yaml for local script execution
    try:
        with open("env.yaml") as f:
            env_vars = yaml.safe_load(f)
            for k, v in env_vars.items():
                os.environ[k] = str(v)
    except Exception:
        print("Could not load env.yaml")

    complete_old_refunds()
