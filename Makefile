.PHONY: generate-ssm test deps

# Usage:
#   make generate-ssm FILE=<circuit file>
# Example: make generate-ssm FILE=circuits/amp1.circuijt
generate-ssm:
	python generate_ssm.py --stdout $(FILE)

test:
	pytest

deps:
	pip install -r requirements.txt
