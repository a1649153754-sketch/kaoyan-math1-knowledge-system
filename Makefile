.PHONY: install serve build test validate identities bundle clean

install:
	python -m pip install -r requirements.txt

serve:
	zensical serve

build:
	zensical build --clean

validate:
	python scripts/validate_project.py

test:
	python -m unittest discover -s tests -p "test_*.py"

identities:
	python scripts/build_released_identities.py --check

bundle:
	python scripts/build_bundle.py

clean:
	rm -rf site dist/*.md
