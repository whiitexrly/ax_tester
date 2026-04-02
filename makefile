.PHONY: format check mcpinspector

# ruff format functions
format:
	ruff format . && ruff check --fix .
	
checkruff:
	ruff format --check && ruff check
