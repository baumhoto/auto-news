from datetime import timedelta, datetime
from textwrap import dedent

# The DAG object; we'll need this to instantiate a DAG
from airflow import DAG

# Operators; we need this to operate!
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.utils.dates import days_ago

# These args will get passed on to each operator
# You can override them on a per-task basis during operator initialization
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email': ['hyzwowtools@gmail.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    # 'queue': 'bash_queue',
    # 'pool': 'backfill',
    # 'priority_weight': 10,
    # 'end_date': datetime(2016, 1, 1),
    # 'wait_for_downstream': False,
    # 'dag': dag,
    # 'sla': timedelta(hours=2),
    # 'execution_timeout': timedelta(seconds=300),
    # 'on_failure_callback': some_function,
    # 'on_success_callback': some_other_function,
    # 'on_retry_callback': another_function,
    # 'sla_miss_callback': yet_another_function,
    # 'trigger_rule': 'all_success'
}


# Important Notes: This DAG must be executed before others, since it
# will create the new embedding table first, then other DAGs can be
# consumed later
with DAG(
    'collection_weekly',
    default_args=default_args,
    max_active_runs=1,
    description='Collect weekly best content. config: {"sources": "Twitter,Article,Youtube,RSS", "targets": "notion", "dedup": true, "min-rating": 4}',
    # schedule_interval=timedelta(minutes=60),
    schedule_interval="30 2 * */1 *",  # At 02:30 weekly
    # schedule_interval=None,
    start_date=days_ago(0, hour=1),
    tags=['NewsBot'],
) as dag:

    t0 = BashOperator(
        task_id='git_pull',
        bash_command='cd ~/airflow/run/auto-news && git pull && git log -1',
    )

    t1 = BashOperator(
        task_id='start',
        bash_command='cd ~/airflow/run/auto-news/src && python3 af_start.py --start {{ ds }} --prefix=./run',
    )

    t2 = BashOperator(
        task_id='prepare',
        bash_command='mkdir -p ~/airflow/data/collect/{{ run_id }}',
    )

    t3 = BashOperator(
        task_id='pull',
        bash_command='cd ~/airflow/run/auto-news/src && python3 af_collect.py '
        '--start {{ ds }} '
        '--prefix=./run '
        '--run-id={{ run_id }} '
        '--job-id={{ ti.job_id }} '
        '--data-folder=data/collect '
        '--collection-type=weekly '
        '--min-rating={{ dag_run.conf.setdefault("min-rating", 4) }} '
        '--sources={{ dag_run.conf.setdefault("sources", "Twitter,Article,Youtube,RSS") }} '
    )

    t4 = BashOperator(
        task_id='save',
        bash_command='cd ~/airflow/run/auto-news/src && python3 af_publish.py '
        '--start {{ ds }} '
        '--prefix=./run '
        '--run-id={{ run_id }} '
        '--job-id={{ ti.job_id }} '
        '--data-folder=data/collect '
        '--sources={{ dag_run.conf.setdefault("sources", "Twitter,Article,Youtube,RSS") }} '
        '--targets={{ dag_run.conf.setdefault("targets", "notion") }} '
        '--collection-type=weekly '
        '--min-rating={{ dag_run.conf.setdefault("publishing-min-rating", 4.5) }} '
    )

    t5 = BashOperator(
        task_id='finish',
        depends_on_past=False,
        bash_command='cd ~/airflow/run/auto-news/src && python3 af_end.py '
        '--start {{ ds }} '
        '--prefix=./run ',
    )

    t0 >> t1 >> t2 >> t3 >> t4 >> t5