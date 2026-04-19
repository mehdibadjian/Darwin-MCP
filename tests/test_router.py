"""Tests for brain.bridge.router — Dynamic Tool Router."""
import pytest
from brain.bridge.router import route_tools, get_routed_tools


SAMPLE_REGISTRY = {
    "skills": {
        "brave_search": {
            "status": "active",
            "short_description": "Search web for real-time facts.",
        },
        "sequential_thinking": {
            "status": "active",
            "short_description": "Break problem into numbered steps.",
        },
        "get_droplet_vitals": {
            "status": "active",
            "short_description": "Get server CPU, RAM, disk stats.",
        },
        "nestjs_best_practices": {
            "status": "active",
            "short_description": "Get NestJS architecture best practices.",
        },
        "fpga_best_practices": {
            "status": "active",
            "short_description": "Get FPGA hardware design best practices.",
        },
        "toxic_tool": {
            "status": "Toxic",
            "short_description": "Should never appear.",
        },
    }
}


def test_route_tools_returns_top_n():
    tools = {k: v for k, v in SAMPLE_REGISTRY["skills"].items() if v["status"] != "Toxic"}
    result = route_tools("search the web for news", tools, top_n=3)
    assert len(result) <= 3


def test_route_tools_relevant_first():
    tools = {k: v for k, v in SAMPLE_REGISTRY["skills"].items() if v["status"] != "Toxic"}
    result = route_tools("search latest news on the web", tools, top_n=3)
    assert "brave_search" in result


def test_route_tools_server_vitals_query():
    tools = {k: v for k, v in SAMPLE_REGISTRY["skills"].items() if v["status"] != "Toxic"}
    result = route_tools("how is the server CPU doing", tools, top_n=3)
    assert "get_droplet_vitals" in result


def test_route_tools_empty_query_returns_top_n():
    tools = {k: v for k, v in SAMPLE_REGISTRY["skills"].items() if v["status"] != "Toxic"}
    result = route_tools("", tools, top_n=2)
    assert len(result) == 2


def test_get_routed_tools_excludes_toxic():
    result = get_routed_tools("anything", SAMPLE_REGISTRY, top_n=10)
    assert "toxic_tool" not in result


def test_get_routed_tools_no_query_returns_up_to_top_n():
    result = get_routed_tools(None, SAMPLE_REGISTRY, top_n=3)
    assert len(result) <= 3
    assert "toxic_tool" not in result


def test_route_tools_empty_registry():
    result = route_tools("some query", {}, top_n=3)
    assert result == {}


def test_route_tools_falls_back_to_description():
    tools = {
        "my_tool": {
            "status": "active",
            "description": "Detailed academic description of a web search utility.",
        }
    }
    result = route_tools("web search", tools, top_n=3)
    assert "my_tool" in result
