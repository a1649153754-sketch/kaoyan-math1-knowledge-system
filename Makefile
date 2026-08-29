.PHONY: install serve build test validate identities exam-index-check local-init local-validate local-report bundle bundle-check clean

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

exam-index-check:
	python scripts/build_exam_evidence_indexes.py --check

local-init:
	python scripts/init_local_data.py

local-validate:
	python scripts/validate_local_data.py

local-report:
	python scripts/generate_local_reports.py

bundle:
	python scripts/build_bundle.py

bundle-check:
	python scripts/check_bundle_deterministic.py

clean:
	rm -rf site dist/*.md
