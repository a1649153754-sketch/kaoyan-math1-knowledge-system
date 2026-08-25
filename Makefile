.PHONY: install serve build validate bundle clean

install:
	python -m pip install -r requirements.txt

serve:
	zensical serve

build:
	zensical build --clean

validate:
	python scripts/validate_project.py

bundle:
	python scripts/build_bundle.py

clean:
	rm -rf site dist/*.md
