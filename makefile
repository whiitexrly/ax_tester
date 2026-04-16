.PHONY: format check mcpinspector

# ruff format functions
format:
	ruff format . && ruff check --fix .
	
checkruff:
	ruff format --check && ruff check

# mcp inspector
mcpinspector:
	bash -c 'trap "kill 0" SIGINT; python mcp_server.py & sleep 2 && npx @modelcontextprotocol/inspector'