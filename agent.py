"""
ADK entrypoint for the ax-tester agent.

This file exposes root_agent for ADK discovery while keeping the implementation
inside src/agent/agent.py.
"""

from agents.static_agent import static_analysis_agent

root_agent = static_analysis_agent
