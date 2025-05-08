.PHONY: generate-ssm test deps detect-shorts

# Usage:
#   make generate-ssm FILE=<circuit_file> [ARGS="--other-options"]
# Example: make generate-ssm FILE=circuits/amp1.circuijt
# Example: make generate-ssm FILE=circuits/amp1.circuijt ARGS="--stdout"
# Example: make generate-ssm FILE=circuits/amp1.circuijt ARGS="--debug-dump"
# Example: make generate-ssm FILE=circuits/amp1.circuijt ARGS="--stdout --debug-dump"
generate-ssm:
	python generate_ssm.py $(FILE) $(ARGS)

test:
	pytest

deps:
	pip install -r requirements.txt

# Usage:
#   make detect-shorts FILE=<circuit_file> [ARGS="--other-options"]
# Example: make detect-shorts FILE=circuits/amp1.circuijt ARGS="--debug-dump"
detect-shorts:
	python detect_shorts.py $(FILE) $(ARGS)