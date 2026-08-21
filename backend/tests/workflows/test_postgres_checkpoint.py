import os
import uuid

import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import START, StateGraph
from psycopg import connect
from psycopg.rows import dict_row
from typing_extensions import TypedDict


class CounterState(TypedDict):
    value: int


@pytest.mark.skipif(
    "OPSPILOT_TEST_POSTGRES_URL" not in os.environ,
    reason="PostgreSQL integration URL is not configured",
)
def test_checkpoint_survives_saver_recreation() -> None:
    url = os.environ["OPSPILOT_TEST_POSTGRES_URL"]
    thread_id = f"checkpoint-{uuid.uuid4()}"
    with connect(url, autocommit=True, prepare_threshold=0, row_factory=dict_row) as first:
        saver = PostgresSaver(first)
        saver.setup()
        builder = StateGraph(CounterState)
        builder.add_node("increment", lambda state: {"value": state["value"] + 1})
        builder.add_edge(START, "increment")
        graph = builder.compile(checkpointer=saver)
        assert graph.invoke(
            {"value": 1}, config={"configurable": {"thread_id": thread_id}}
        )["value"] == 2

    with connect(url, autocommit=True, prepare_threshold=0, row_factory=dict_row) as restarted:
        recovered = PostgresSaver(restarted).get(
            {"configurable": {"thread_id": thread_id}}
        )
        assert recovered is not None
        assert recovered["channel_values"]["value"] == 2
