.PHONY: dev install test run build clean

dev:
	pip install -e ".[dev]"

install:
	pip install -e .

test:
	python -m pytest tests/ -v

run:
	python -m dxc_doctor

build:
	cd build && bash build.sh

clean:
	rm -rf dist/ build/output/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
